from flask.ext.restful import Resource, reqparse, fields, marshal_with, inputs, marshal
from webservices.common.models import db, Candidate, Committee, CandidateCommitteeLink, CommitteeDetail
from webservices.common.util import Pagination
from sqlalchemy.sql import text, or_, and_
from sqlalchemy import extract
from datetime import date

# output format for flask-restful marshaling
candidate_commitee_fields = {
    'candidate_id': fields.String,
    'candidate_name': fields.String,
    'active_through': fields.Integer,
    'link_date': fields.String,
    'expire_date': fields.String,
}
committee_fields = {
    'committee_id': fields.String,
    'name': fields.String,
    'designation_full': fields.String,
    'designation': fields.String,
    'treasurer_name': fields.String,
    'organization_type_full': fields.String,
    'organization_type': fields.String,
    'state': fields.String,
    'party_full': fields.String,
    'party': fields.String,
    'committee_type_full': fields.String,
    'committee_type': fields.String,
    'expire_date': fields.String,
    'first_file_date': fields.String,
    'last_file_date': fields.String,
    'candidates': fields.Nested(candidate_commitee_fields),
}
committee_detail_fields = {
    'committee_id': fields.String,
    'name': fields.String,
    'designation_full': fields.String,
    'designation': fields.String,
    'treasurer_name': fields.String,
    'organization_type_full': fields.String,
    'organization_type': fields.String,
    'state': fields.String,
    'party_full': fields.String,
    'party': fields.String,
    'committee_type_full': fields.String,
    'committee_type': fields.String,
    'expire_date': fields.String,
    'first_file_date': fields.String,
    'last_file_date': fields.String,
    'candidates': fields.Nested(candidate_commitee_fields),
    'filing_frequency' : fields.String,
    'email' : fields.String,
    'fax' : fields.String,
    'website' : fields.String,
    'form_type' : fields.String,
    'leadership_pac' : fields.String,
    'load_date' : fields.String,
    'lobbyist_registrant_pac' : fields.String,
    'party_type' : fields.String,
    'party_type_full' : fields.String,
    'qualifying_date' : fields.String,
    'street_1' : fields.String,
    'street_2' : fields.String,
    'city' : fields.String,
    'state_full' : fields.String,
    'zip' : fields.String,
    'treasurer_city' : fields.String,
    'treasurer_name_1' : fields.String,
    'treasurer_name_2' : fields.String,
    'treasurer_name_middle' : fields.String,
    'treasurer_name_prefix' : fields.String,
    'treasurer_phone' : fields.String,
    'treasurer_state' : fields.String,
    'treasurer_street_1' : fields.String,
    'treasurer_street_2' : fields.String,
    'treasurer_name_suffix' : fields.String,
    'treasurer_name_title' : fields.String,
    'treasurer_zip' : fields.String,
    'custodian_city' : fields.String,
    'custodian_name_1' : fields.String,
    'custodian_name_2' : fields.String,
    'custodian_name_middle' : fields.String,
    'custodian_name_full' : fields.String,
    'custodian_phone' : fields.String,
    'custodian_name_prefix' : fields.String,
    'custodian_state' : fields.String,
    'custodian_street_1' : fields.String,
    'custodian_street_2' : fields.String,
    'custodian_name_suffix' : fields.String,
    'custodian_name_title' : fields.String,
    'custodian_zip' : fields.String,
}
pagination_fields = {
    'per_page': fields.Integer,
    'page': fields.Integer,
    'count': fields.Integer,
    'pages': fields.Integer,
}
committee_list_fields = {
    'api_version': fields.Fixed(1),
    'pagination': fields.Nested(pagination_fields),
    'results': fields.Nested(committee_fields),
}


def filter_year(model, query, years):
    return query.filter(
        or_(*[
            and_(
                or_(
                    extract('year', model.last_file_date) >= year,
                    model.last_file_date == None,
                ),
                extract('year', model.first_file_date) <= year,
            )
            for year in years
        ])
    )  # noqa


class CommitteeList(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('q', type=str, help='Text to search all fields for')
    parser.add_argument('committee_id', type=str, action='append', help="Committee's FEC ID")
    parser.add_argument('candidate_id', type=str, action='append', help="Candidate's FEC ID")
    parser.add_argument('state', type=str, action='append', help='Two digit U.S. State committee is registered in')
    parser.add_argument('name', type=str, help="Committee's name (full or partial)")
    parser.add_argument('page', type=int, default=1, help='For paginating through results, starting at page 1')
    parser.add_argument('per_page', type=int, default=20, help='The number of results returned per page. Defaults to 20.')
    parser.add_argument('committee_type', type=str, action='append', help='The one-letter type code of the organization')
    parser.add_argument('designation', type=str, action='append', help='The one-letter designation code of the organization')
    parser.add_argument('organization_type', type=str, action='append', help='The one-letter code for the kind for organization')
    parser.add_argument('party', type=str, action='append', help='Three letter code for party')
    parser.add_argument('year', type=int, action='append', help='A year that the committee was active- (after original registration date but before expiration date.)')
    parser.add_argument('cycle', type=int, action='append', help='An election cycle that the committee was active- (after original registration date but before expiration date.)')
    # not implemented yet
    # parser.add_argument('expire_date', type=str, help='Date the committee registration expires')
    # parser.add_argument('original_registration_date', type=str, help='Date of the committees first registered')

    @marshal_with(committee_list_fields)
    def get(self):

        args = self.parser.parse_args(strict=True)

        # pagination
        page_num = args.get('page', 1)
        per_page = args.get('per_page', 20)

        count, committees = self.get_committees(args, page_num, per_page)

        page_data = Pagination(page_num, per_page, count)

        data = {
            'api_version': '0.2',
            'pagination': page_data.as_json(),
            'results': committees
        }

        return data


    def get_committees(self, args, page_num, per_page):

        committees = Committee.query

        if args['candidate_id']:
            committees = committees.filter(Committee.candidate_ids.overlap(args['candidate_id']))

        elif args.get('q'):
            fulltext_qry = """SELECT cmte_sk
                              FROM   dimcmte_fulltext_mv
                              WHERE  fulltxt @@ to_tsquery(:findme)
                              ORDER BY ts_rank_cd(fulltxt, to_tsquery(:findme)) desc"""

            findme = ' & '.join(args['q'].split())
            committees = committees.filter(Committee.committee_key.in_(
                db.session.query("cmte_sk").from_statement(text(fulltext_qry)).params(findme=findme)))

        for argname in ['committee_id', 'designation', 'organization_type', 'state', 'party', 'committee_type']:
            if args.get(argname):
                committees = committees.filter(getattr(Committee, argname).in_(args[argname]))

        if args.get('name'):
            committees = committees.filter(Committee.name.ilike('%{}%'.format(args['name'])))

        if args['year']:
            committees = filter_year(Committee, committees, args['year'])

        if args['cycle']:
            committees = committees.filter(Committee.cycles.overlap(args['cycle']))

        count = committees.count()

        return count, committees.order_by(Committee.name).paginate(page_num, per_page, False).items



class CommitteeView(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('page', type=int, default=1, help='For paginating through results, starting at page 1')
    parser.add_argument('per_page', type=int, default=20, help='The number of results returned per page. Defaults to 20.')
    parser.add_argument('year', type=int, action='append', help='A year that the committee was active- (after original registration date but before expiration date.)')
    parser.add_argument('cycle', type=int, action='append', help='An election cycle that the committee was active- (after original registration date but before expiration date.)')
    # useful for lookup by candidate id
    parser.add_argument('designation', type=str, action='append', help='The one-letter designation code of the organization')
    parser.add_argument('organization_type', type=str, action='append', help='The one-letter code for the kind for organization')
    parser.add_argument('committee_type', type=str, action='append', help='The one-letter type code of the organization')

    def get(self, **kwargs):

        if 'committee_id' in kwargs:
            committee_id = kwargs['committee_id']
            candidate_id = None
        else:
            committee_id = None
            candidate_id = kwargs['candidate_id']

        args = self.parser.parse_args(strict=True)

        # pagination
        page_num = args.get('page', 1)
        per_page = args.get('per_page', 20)

        count, committees = self.get_committee(args, page_num, per_page, committee_id, candidate_id)

        page_data = Pagination(page_num, per_page, count)

        # decorator won't work for me
        committees = marshal(committees, committee_detail_fields)

        data = {
            'api_version': '0.2',
            'pagination': page_data.as_json(),
            'results': committees
        }

        return data


    def get_committee(self, args, page_num, per_page, committee_id, candidate_id):

        if committee_id is not None:
            committees = CommitteeDetail.query
            committees = committees.filter_by(**{'committee_id': committee_id})

        if candidate_id is not None:
            committees = CommitteeDetail.query.join(CandidateCommitteeLink).filter(CandidateCommitteeLink.candidate_id==candidate_id)

        for argname in ['designation', 'organization_type', 'committee_type']:
            if args.get(argname):
                committees = committees.filter(getattr(CommitteeDetail, argname).in_(args[argname]))

        if args['year']:
            committees = filter_year(CommitteeDetail, committees, args['year'])

        if args['cycle']:
            committees = committees.filter(CommitteeDetail.cycles.overlap(args['cycle']))

        count = committees.count()

        return count, committees.order_by(CommitteeDetail.name).paginate(page_num, per_page, False).items
