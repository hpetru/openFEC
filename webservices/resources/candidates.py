from flask.ext.restful import Resource, reqparse, fields, marshal_with, inputs, marshal
from webservices.common.models import db, Candidate, CandidateDetail, Committee, CandidateCommitteeLink, CandidateHistory
from webservices.common.util import Pagination
from sqlalchemy.sql import text, or_
from sqlalchemy import extract

# output format for flask-restful marshaling
candidate_commitee_fields = {
    'committee_id': fields.String,
    'committee_name': fields.String,
    'link_date': fields.String,
    'expire_date': fields.String,
    'committee_type': fields.String,
    'committee_type_full': fields.String,
    'committee_designation': fields.String,
    'committee_designation_full': fields.String,
    'election_year': fields.Integer,
}
candidate_fields = {
    'candidate_id': fields.String,
    'candidate_status_full': fields.String,
    'candidate_status': fields.String,
    'district': fields.String,
    'active_through': fields.Integer,
    'election_years': fields.List(fields.Integer),
    'cycles': fields.List(fields.Integer),
    'incumbent_challenge_full': fields.String,
    'incumbent_challenge': fields.String,
    'office_full': fields.String,
    'office': fields.String,
    'party_full': fields.String,
    'party': fields.String,
    'state': fields.String,
    'name': fields.String,
}
candidate_detail_fields = {
    'candidate_id': fields.String,
    'candidate_status_full': fields.String,
    'candidate_status': fields.String,
    'district': fields.String,
    'active_through': fields.Integer,
    'election_years': fields.List(fields.Integer),
    'incumbent_challenge_full': fields.String,
    'incumbent_challenge': fields.String,
    'office_full': fields.String,
    'office': fields.String,
    'party_full': fields.String,
    'party': fields.String,
    'state': fields.String,
    'name': fields.String,
    'expire_date': fields.String,
    'load_date': fields.String,
    'form_type': fields.String,
    'address_city': fields.String,
    'address_state': fields.String,
    'address_street_1': fields.String,
    'address_street_2': fields.String,
    'address_zip': fields.String,
    'candidate_inactive': fields.String,
    'committees': fields.Nested(candidate_commitee_fields),
}
candidate_history_fields = {
    'candidate_id': fields.String,
    'two_year_period': fields.Integer,
    'candidate_status_full': fields.String,
    'candidate_status': fields.String,
    'district': fields.String,
    'incumbent_challenge_full': fields.String,
    'incumbent_challenge': fields.String,
    'office_full': fields.String,
    'office': fields.String,
    'party_full': fields.String,
    'party': fields.String,
    'state': fields.String,
    'name': fields.String,
    'expire_date': fields.String,
    'load_date': fields.String,
    'form_type': fields.String,
    'address_city': fields.String,
    'address_state': fields.String,
    'address_street_1': fields.String,
    'address_street_2': fields.String,
    'address_zip': fields.String,
    'candidate_inactive': fields.String,
}
pagination_fields = {
    'per_page': fields.Integer,
    'page': fields.Integer,
    'count': fields.Integer,
    'pages': fields.Integer,
}
candidate_list_fields = {
    'api_version': fields.Fixed(1),
    'pagination': fields.Nested(pagination_fields),
    'results': fields.Nested(candidate_fields),
}


class CandidateList(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('q', type=str, help='Text to search all fields for')
    parser.add_argument('candidate_id', type=str, action='append', help="Candidate's FEC ID")
    parser.add_argument('fec_id', type=str, help="Candidate's FEC ID")
    parser.add_argument('page', type=inputs.natural, default=1, help='For paginating through results, starting at page 1')
    parser.add_argument('per_page', type=inputs.natural, default=20, help='The number of results returned per page. Defaults to 20.')
    parser.add_argument('name', type=str, help="Candidate's name (full or partial)")
    parser.add_argument('office', type=str, action='append', help='Governmental office candidate runs for')
    parser.add_argument('state', type=str, action='append', help='U. S. State candidate is registered in')
    parser.add_argument('party', type=str, action='append', help="Three letter code for the party under which a candidate ran for office")
    parser.add_argument('cycle', type=int, action='append', help='Filter records to only those that were applicable to a given election cycle')
    parser.add_argument('district', type=str, action='append', help='Two digit district number')
    parser.add_argument('candidate_status', type=str, action='append', help='One letter code explaining if the candidate is a present, future or past candidate')
    parser.add_argument('incumbent_challenge', type=str, action='append', help='One letter code explaining if the candidate is an incumbent, a challenger, or if the seat is open.')

    @marshal_with(candidate_list_fields)
    def get(self, **kwargs):

        args = self.parser.parse_args(strict=True)

        # pagination
        page_num = args.get('page', 1)
        per_page = args.get('per_page', 20)

        count, candidates = self.get_candidates(args, page_num, per_page)

        page_data = Pagination(page_num, per_page, count)

        data = {
            'api_version': '0.2',
            'pagination': page_data.as_json(),
            'results': candidates
        }

        return data

    def get_candidates(self, args, page_num, per_page):
        candidates = Candidate.query

        fulltext_qry = """SELECT cand_sk
                          FROM   dimcand_fulltext_mv
                          WHERE  fulltxt @@ to_tsquery(:findme)
                          ORDER BY ts_rank_cd(fulltxt, to_tsquery(:findme)) desc"""

        if args.get('q'):
            findme = ' & '.join(args['q'].split())
            candidates = candidates.filter(Candidate.candidate_key.in_(
                db.session.query("cand_sk").from_statement(text(fulltext_qry)).params(findme=findme)))

        for argname in ['candidate_id', 'candidate_status', 'district', 'incumbent_challenge', 'office', 'party', 'state']:
            if args.get(argname):
                # this is not working and doesn't look like it would work for _short
                candidates = candidates.filter(getattr(Candidate, argname).in_(args[argname]))

        if args.get('name'):
            candidates = candidates.filter(Candidate.name.ilike('%{}%'.format(args['name'])))

        # TODO(jmcarp) Reintroduce year filter pending accurate `load_date` and `expire_date` values
        if args['cycle']:
            candidates = candidates.filter(Candidate.cycles.overlap(args['cycle']))

        count = candidates.count()

        return count, candidates.order_by(Candidate.name).paginate(page_num, per_page, False).items



class CandidateView(Resource):

    parser = reqparse.RequestParser()
    parser.add_argument('page', type=inputs.natural, default=1, help='For paginating through results, starting at page 1')
    parser.add_argument('per_page', type=inputs.natural, default=20, help='The number of results returned per page. Defaults to 20.')
    parser.add_argument('office', type=str, action='append', help='Governmental office candidate runs for')
    parser.add_argument('state', type=str, action='append', help='U. S. State candidate is registered in')
    parser.add_argument('party', type=str, action='append', help="Three letter code for the party under which a candidate ran for office")
    parser.add_argument('cycle', type=int, action='append', help='Filter records to only those that were applicable to a given election cycle')
    parser.add_argument('district', type=str, action='append', help='Two digit district number')
    parser.add_argument('candidate_status', type=str, action='append', help='One letter code explaining if the candidate is a present, future or past candidate')
    parser.add_argument('incumbent_challenge', type=str, action='append', help='One letter code explaining if the candidate is an incumbent, a challenger, or if the seat is open.')


    def get(self, **kwargs):
        if 'candidate_id' in kwargs:
            committee_id = None
            candidate_id = kwargs['candidate_id']
        else:
            committee_id = kwargs['committee_id']
            candidate_id = None

        args = self.parser.parse_args(strict=True)

        page_num = args.get('page', 1)
        per_page = args.get('per_page', 20)

        count, candidates = self.get_candidate(args, page_num, per_page, candidate_id, committee_id)

        page_data = Pagination(page_num, per_page, count)

        # decorator won't work for me
        candidates = marshal(candidates, candidate_detail_fields)

        data = {
            'api_version': '0.2',
            'pagination': page_data.as_json(),
            'results': candidates
        }

        return data

    def get_candidate(self, args, page_num, per_page, candidate_id, committee_id):
        if candidate_id is not None:
            candidates = CandidateDetail.query
            candidates = candidates.filter_by(**{'candidate_id': candidate_id})

        if committee_id is not None:
            candidates = CandidateDetail.query.join(CandidateCommitteeLink).filter(CandidateCommitteeLink.committee_id==committee_id)

        for argname in ['candidate_id', 'candidate_status', 'district', 'incumbent_challenge', 'office', 'party', 'state']:
            if args.get(argname):
                # this is not working and doesn't look like it would work for _short
                candidates = candidates.filter(getattr(CandidateDetail, argname).in_(args[argname]))

        # TODO(jmcarp) Reintroduce year filter pending accurate `load_date` and `expire_date` values
        if args['cycle']:
            candidates = candidates.filter(CandidateDetail.cycles.overlap(args['cycle']))

        count = candidates.count()

        return count, candidates.order_by(CandidateDetail.expire_date.desc()).paginate(page_num, per_page, False).items


class CandidateHistoryView(Resource):

    parser = reqparse.RequestParser()
    parser.add_argument('page', type=inputs.natural, default=1, help='For paginating through results, starting at page 1')
    parser.add_argument('per_page', type=inputs.natural, default=20, help='The number of results returned per page. Defaults to 20.')


    def get(self, **kwargs):
        candidate_id = kwargs['candidate_id']
        args = self.parser.parse_args(strict=True)

        page_num = args.get('page', 1)
        per_page = args.get('per_page', 20)


        count, candidates = self.get_candidate(args, page_num, per_page, **kwargs)

        # decorator won't work for me
        candidates = marshal(candidates, candidate_history_fields)

        page_data = Pagination(page_num, per_page, count)

        data = {
            'api_version': '0.2',
            'pagination': page_data.as_json(),
            'results': candidates
        }

        return data

    def get_candidate(self, args, page_num, per_page, **kwargs):
        candidate_id = kwargs['candidate_id']
        year = kwargs.get('year', None)

        candidates = CandidateHistory.query
        candidates = candidates.filter_by(**{'candidate_id': candidate_id})

        if year:
            if year == 'recent':
                candidates = candidates.order_by(CandidateHistory.two_year_period.desc()).first()

                return 1, [candidates]

            else:
                # look for 2 year period
                year = int(year) + int(year) % 2
                candidates = candidates.filter_by(**{'two_year_period': year})

        count = candidates.count()

        return count, candidates.order_by(CandidateHistory.two_year_period.desc()).paginate(page_num, per_page, False).items
