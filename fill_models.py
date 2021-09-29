from configuration import *

models = {
    'project.task.type': {},        # 36,   14-1
    'project.category': {           # 259   1   , 3 duplicates in source
        'model': 'project.tags'},
    'project.project': {},          # 46,   5-2
    'project.task': {},             # 4080, 56-4
    'account.analytic.account': {   # 45
        'domain': [('id', '=', sorted(set([x.get('analytic_account_id')[0] for x in source.env['project.project'].search_read([], ['analytic_account_id'])])))]},  # 59,
    'project.task.work': {          # 6232
        'model': 'account.analytic.line',
        'domain': [('hr_analytic_timesheet_id', '!=', False)]},
    'mail.message': {               # 35627, 9 messages have res_id as 0
        'domain': [('model', '=', 'project.task'), ('res_id', '!=', False)]},
    'project.sprint.type': {},      # 3
    'project.scrum.actors': {},     # 0
    'project.scrum.portfolio': {},  # 18,   6-1
    'project.scrum.sprint': {},     # 138,  3-1
    'project.scrum.us': {},         # 1,    2-1
    'project.scrum.timebox': {},    # 87,   1-1
    'project.scrum.test': {},       # 0
}

for s in models:
    try:
        domain = models.get(s).get('domain', [])
        s_count = len(source.env[s].search(domain))
        print('source model', s, s_count)
        t = models.get(s).get('model', s)
        t_count = len(target.env[t].search([]))
        print('target model', t, t_count)
        m_count = len(target.env['ir.model.data'].find_all_ids_in_target(t))
        print('migrated', m_count)
        if m_count < s_count:
            print(colored(f"missing {t} {s_count-m_count}", 'red'))
        else:
            print(colored('complete', 'green'))
    except:
        input(f'{s} or {t} is missing probably...Press Enter to continue')


migrate_model('project.task.type')

for _id in sorted(source.env['project.category'].search([])):
    migrate_model('project.category', ids=[_id], model2='project.tags')

# source.env['project.category'].search([('name', '=', 'packning')])      # [76, 77]
# source.env['project.category'].search([('name', '=', 'El')])            # [96, 100]
# source.env['project.category'].search([('name', '=', 'Release 1')])     # [259, 260]
# source.env['project.category'].search([('name', '=', 'Dokumentation')]) # [25, 266]
create_xmlid('project.tags',
             get_target_id_from_source_id('project.tags', 76), 77)
create_xmlid('project.tags',
             get_target_id_from_source_id('project.tags', 96), 100)
create_xmlid('project.tags',
             get_target_id_from_source_id('project.tags', 259), 260)
create_xmlid('project.tags',
             get_target_id_from_source_id('project.tags', 25), 266)


'project.project'
project_calc = {'privacy_visibility': """
vals.update(
    {fields[key]: 'portal' if record[key] in ['public'] else record[key]})"""}
migrate_model('project.project', calc=project_calc)


'account.analytic.account mapping'
for pid in source.env['project.project'].search([], order='id'):
    source_id = source.env['project.project'].read(
        pid, ['analytic_account_id'])['analytic_account_id'][0]
    pid_target = get_target_id_from_source_id('project.project', pid)
    target_id = target.env['project.project'].read(
        pid_target, ['analytic_account_id'])[0]['analytic_account_id'][0]
    create_xmlid('account.analytic.account', target_id, source_id)


'project.task'
# project_ids = [30, 55] # priority projects
task_calc = {'priority': """if key in fields:
        vals.update({fields[key]: '0' if record[key] in ['0','1'] else '1'})""",
             'categ_ids': """vals.update({'tag_ids':[get_target_id_from_source_id('project.tags',_id) for _id in record[key]]})"""
             }
task_context = {'mail_create_nosubscribe': True,
                'mail_create_nolog': True,
                'mail_notrack': True,
                'tracking_disable': True}
task_diff = {'categ_ids': 'tag_ids',
             'date_start': 'date_assign'}
task_domain = [('project_id', '!=', 55)]
migrate_model('project.task',
              calc=task_calc,
              context=task_context,
              create=1,
              diff=task_diff,
              domain=task_domain,
              exclude=['message_follower_ids'],
              )


migrate_model('project.scrum.actors')   # empty
migrate_model('project.scrum.meeting')  # empty
migrate_model('project.scrum.test')     # empty
migrate_model('project.scrum.us')       # 1 record
migrate_model('project.scrum.portfolio')
migrate_model('project.scrum.sprint')
migrate_model('project.scrum.timebox')


'project.task.work -> account.analytic.line'
create = 1
line_ids = target.env['ir.model.data'].find_all_ids_in_target(
    'account.analytic.line')
task_records = {x.get('id'): x for x in source.env['project.task'].search_read(
    [], ['project_id'])}
timesheet_records = {x.get('id'): x for x in source.env['hr.analytic.timesheet'].search_read(
    [], ['line_id'], order='id')}
user_records = {x.get('id'): x for x in source.env['res.users'].search_read(
    [], ['employee'], order='id')}
work_records = {x.get('id'): x for x in source.env['project.task.work'].search_read(
    [('hr_analytic_timesheet_id', '!=', False)], ['hr_analytic_timesheet_id', 'task_id', 'user_id'], order='id')}
for work_id in work_records:
    work_record = work_records.get(work_id)
    timesheet = work_record.get('hr_analytic_timesheet_id')
    line = timesheet_records.get(timesheet[0]).get('line_id')
    if line:
        line = line[0]

    if line in line_ids and create:
        continue

    vals = {}

    task = work_record.get('task_id')
    if task:
        task = task[0]
        vals.update(
            {'task_id': get_target_id_from_source_id('project.task', task)})

        task_record = task_records.get(task)

        employee = False
        user = work_record.get('user_id')
        if user:
            user_record = user_records.get(user[0])

            employee = user_record.get('employee')
            if employee:
                employee = get_target_id_from_source_id(
                    'hr.employee', employee[0])

        vals.update(
            {'employee_id': employee})

        project = task_record.get('project_id')
        if project:
            vals.update(
                {'project_id': get_target_id_from_source_id('project.project', project[0])})

    print(vals)
    migrate_model('account.analytic.line',
                  context=task_context,
                  create=create,
                  custom=vals,
                  ids=[line])
    line_ids.append(line)


create = 1
migrated_message_ids = target.env['ir.model.data'].find_all_ids_in_target(
    'mail.message')
task_context = {'mail_create_nosubscribe': True,
                'mail_create_nolog': True,
                'mail_notrack': True,
                'tracking_disable': True}
task_domain = [('project_id', '!=', 55)]
task_records = {x.get('id'): x for x in source.env['project.task'].search_read(
    task_domain, ['message_ids'], order='id')}
for task_id in task_records:
    task_record = task_records.get(task_id)
    message_ids = sorted(task_record.get('message_ids'))
    to_migrate = []
    for message_id in message_ids:
        if create:
            if message_id in migrated_message_ids:
                print(message_id, 'is migrated, skipping creation')
                continue
            to_migrate.append(message_id)
        else:
            if message_id not in migrated_message_ids:
                print(message_id, 'is not migrated yet, write failed')
                continue
            to_migrate.append(message_id)

    if to_migrate:
        print(to_migrate)
        target_id = get_target_id_from_source_id('project.task', task_id)
        migrate_model('mail.message',
                      context=task_context,
                      create=create,
                      custom={'res_id': target_id},
                      exclude=['notified_partner_ids', 'tracking_value_ids'],
                      ids=to_migrate)
    else:
        continue
    print(f"Recordset('project.task', [{task_id}]).message_ids DONE!")


"""


# Install 'en_US' for res.partner


Kontakter
migrate_model('res.bank')
migrate_model('res.partner.category', create=False)
migrate_model('res.partner.category')
migrate_model('res.partner.title', create=False)
migrate_model('res.partner.title')
migrate_model('res.partner', create=False,
              diff={'image': 'image_1920'},
              exclude=['email_formatted'])
migrate_model('res.partner',
              diff={'image': 'image_1920'},
              exclude=['email_formatted'])
migrate_model('res.company', create=False,
              include=['company_registry', 'social_github'],)
migrate_model('res.partner.bank')


Anställda
migrate_model('hr.department', create=False)
migrate_model('hr.department')
migrate_model('hr.employee.category', create=False)
migrate_model('hr.employee.category')
migrate_model('hr.job', create=False)
migrate_model('hr.job')
migrate_model('hr.leave.type')
migrate_model('hr.employee', diff={'image': 'image_1920'}, create=False)
migrate_model('hr.employee', diff={'image': 'image_1920'})
migrate_model('hr.attendance')


Inställningar
migrate_model('res.users',
              context={'install_mode': True, 'no_reset_password': True},
              custom={'active': True,
                      'signup_token': False,
                      'signup_type': False,
                      'signup_valid': False,
                      },
              diff={'image': 'image_1920'},
              exclude=['email_formatted'],)
migrate_model('res.users',
              create=False,
              context={'install_mode': True, 'no_reset_password': True},
              include=['active'],)
migrate_model('hr.employee', diff={
              'image': 'image_1920'}, create=False, include=['image'])  # image fix
migrate_model('resource.calendar')
migrate_model('resource.calendar.attendance')
migrate_model('resource.calendar.leaves')  # depends hr.leave
migrate_model('ir.attachment', exclude=['res_id'])
migrate_model('ir.attachment', ids=[1743], exclude=['datas', 'res_id'])
migrate_model('ir.attachment', exclude=['res_id'])
migrate_model('ir.attachment', ids=[1749], exclude=['datas', 'res_id'])
migrate_model('ir.attachment', exclude=['res_id'])
migrate_model('ir.attachment', ids=[1750], exclude=['datas', 'res_id'])
migrate_model('ir.attachment', exclude=['res_id'])
migrate_model('res.partner', create=False,
              include = ['opportunity_ids',  # crm.lead
                       'commercial_partner_id',  # res.partner
                       'message_partner_ids',  # res.partner
                       'message_main_attachment_id',  # ir.attachment
                       'team_id',  # crm.team
                       'user_id',  # res.users
                       ])


migrate_model('utm.campaign', create = False)
migrate_model('utm.campaign')
migrate_model('utm.medium', create = False)
migrate_model('utm.medium')
migrate_model('utm.source', create = False)
migrate_model('utm.source')
migrate_model('account.analytic.account')
migrate_model('account.analytic.line')


Rekrytering
# migrate_model('mail.activity.type', create=False)
migrate_model('mail.activity.type')
# migrate_model('hr.recruitment.stage', create=False)
migrate_model('hr.recruitment.stage')
# migrate_model('hr.recruitment.degree', create=False)
migrate_model('hr.recruitment.degree')
# migrate_model('hr.applicant.category', create=False)
migrate_model('hr.applicant.category')
# migrate_model('hr.applicant', create=False)
migrate_model('hr.applicant')


Projekt
migrate_model('project.assignment')
# migrate_model('project.role', create=False)
migrate_model('project.role')
migrate_model('project.tags')
migrate_model('project.task.type')
migrate_model('project.project',
              exclude = ['rating_status', 'rating_status_period'])
migrate_model('project.task')
migrate_model('project.task', create = False,
              include = ['parent_id',  # project.task
                       'dependency_task_ids',  # project.task
                       'recursive_dependency_task_ids',  # project.task
                       'timesheet_ids ',  # account.analytic.line
                       'timesheet_product_id',  # product.product
                       ])
migrate_model('project.project', create = False,
              include = ['favorite_user_ids'])
migrate_model('project.task')


Maintenance
# migrate_model('maintenance.team') # only 1 team
migrate_model('maintenance.stage')
migrate_model('maintenance.equipment.category')
migrate_model('maintenance.equipment')
migrate_model('maintenance.request')


Helpdesk
migrate_model('mail.template')
# migrate_model('helpdesk.ticket.category', create=False)
migrate_model('helpdesk.ticket.category')
# migrate_model('helpdesk.ticket.channel', create=False)
migrate_model('helpdesk.ticket.channel')
# migrate_model('helpdesk.ticket.stage', create=False)
migrate_model('helpdesk.ticket.stage')
# migrate_model('helpdesk.ticket.tag', create=False)
migrate_model('helpdesk.ticket.tag')
# migrate_model('helpdesk.ticket.team', create=False)
migrate_model('helpdesk.ticket.team')
# migrate_model('helpdesk.ticket', create=False)
migrate_model('helpdesk.ticket')


Försäljning
migrate_model('account.tax')
migrate_model('product.product')
migrate_model('product.category')
migrate_model('product.product', create = False, include = ['list_price'])
migrate_model('product.pricelist')
migrate_model('product.pricelist.item')
migrate_model('sale.order')
migrate_model('sale.order.line')
migrate_model('sale.order.option')
migrate_model('sale.order.template', custom = {'company_id': 1})
migrate_model('sale.order.template.line', custom = {'company_id': 1})
migrate_model('sale.order.template.option', custom = {'company_id': 1})


Kundvård
migrate_model('crm.lead.tag', model2 = 'crm.tag')
migrate_model('crm.lost.reason')
migrate_model('crm.phonecall')
migrate_model('crm.stage')
migrate_model('crm.team')
migrate_model('crm.lead')


Kalender
migrate_model('calendar.alarm')
migrate_model('calendar.event.type')
migrate_model('calendar.contacts')
migrate_model('calendar.event', command = {'partner_ids': 6},
              context = {'virtual_id': False},)
migrate_model('calendar.event', command = {'partner_ids': 6},
              ids = [151], custom = {'privacy': 'public', 'show_as': 'busy'})  # some fields were null
migrate_model('calendar.event', command = {'partner_ids': 6})
migrate_model('calendar.attendee')


Ledighet
migrate_model('hr.leave.type')
migrate_model('hr.leave.type', create = False,
              custom = {'validity_start': False, 'validity_stop': False}, include = ['validity_stop'])  # temporarily allow old entries to be created
migrate_model('hr.leave.allocation')
migrate_model('hr.leave.allocation', create = False,
              include = [
                  'linked_request_ids',  # hr.leave.allocation
                  'parent_id',  # hr.leave.allocation
              ])
migrate_model('hr.leave',
              domain = [('id', '!=', 316)],  # conflicts with 315
              exclude = ['state'])  # cannot create with 'validate' state
migrate_model('hr.leave', create = False,
              domain = [('id', '!=', 316)],  # conflicts with 315
              include = ['state'])  # change to correct state
migrate_model('hr.leave.type', create = False,)  # restore validity_stop


Tidrapporter
ids=sorted(source.env['hr_timesheet.sheet'].search([]))
for _id in ids:
    migrate_model('hr_timesheet.sheet',
                  context = {'skip_check_state': True},
                  create = False,
                  ids = [_id])


# depends mail.activity.type, calendar.event, mail.template, note.note
migrate_model('mail.activity.type')
migrate_model('mail.activity')  # maintenance.request
migrate_model('mail.channel', command = {'channel_partner_ids': 6})
migrate_model('mail.message.subtype')
migrate_model('mail.message.subtype', create = False,
              ids = [int(target.env['ir.model.data'].browse(id).complete_name.split('_')[-1]) for id in target.env['ir.model.data'].search(
                  [('model', '=', 'mail.message.subtype'), ('module', '=', '__import__')])],
              include = ['parent_id'])
migrate_model('res.partner', create = False, include = ['channel_ids'])
for id in sorted(source.env['mail.followers'].search([])):
    try:
        migrate_model('mail.followers', ids = [id])
    except:
        continue


Anteckningar
migrate_model('note.stage')
migrate_model('note.tag')
migrate_model('note.note')  # exclude=['user_id'])
migrate_model('note.note', create = False)
migrate_model('resource.calendar')
migrate_model('rating.rating')


Uppdatera
# domain = [('write_date', '>', '2021-06-23')]
domain=[('write_date', '>', '2021-06-01')]
migrate_model('res.partner', create = False,
              diff = {'image': 'image_1920'}, domain = domain,
              exclude = ['email_formatted'])
migrate_model('res.partner',
              diff = {'image': 'image_1920'}, domain = domain,
              exclude = ['email_formatted'])
migrate_model('hr.employee', create = False,
              diff = {'image': 'image_1920'}, domain = domain)
migrate_model('hr.employee', diff = {'image': 'image_1920'}, domain = domain)
migrate_model('res.users', create = False,
              command = {'groups_id': 6},
              context = {'install_mode': True, 'no_reset_password': True}, domain = domain,
              exclude = ['email_formatted', 'signup_token', 'signup_type', 'signup_valid', ])
migrate_model('hr_timesheet.sheet',
              context = {'skip_check_state': True},
              create = False,
              domain = domain,
              exclude = ['message_follower_ids'])
migrate_model('hr_timesheet.sheet',
              context = {'skip_check_state': True},
              domain = domain,
              exclude = ['message_follower_ids'])
migrate_model('account.analytic.account', create = False, domain = domain)
migrate_model('account.analytic.account', domain = domain)
migrate_model('account.analytic.line', context = {
              'skip_check_state': True}, create = False, domain = domain)
migrate_model('account.analytic.line', context = {
              'skip_check_state': True}, domain = domain)
migrate_model('note.note', create = False, domain = domain)
migrate_model('note.note', domain = domain, exclude = ['user_id'])
migrate_model('sale.order', create = False, domain = domain)
migrate_model('sale.order', domain = domain)
migrate_model('sale.order.line', create = False, domain = domain)
migrate_model('sale.order.line', domain = domain)
# migrate_model('maintenance.request', create=False,
#               domain=domain, exclude=['message_follower_ids'])
# migrate_model('maintenance.request', domain=domain,
#               exclude=['message_follower_ids'])
migrate_model('calendar.event', create = False,
              command = {'partner_ids': 6},
              context = {'virtual_id': False},
              domain = domain,
              exclude = ['message_follower_ids'])
migrate_model('calendar.event',
              command = {'partner_ids': 6},
              context = {'virtual_id': False},
              domain = domain)
migrate_model('hr.leave',
              domain = domain+[('id', '!=', 316)],  # conflicts with 315
              exclude = ['state'])  # cannot create with 'validate' state
migrate_model('hr.leave', create = False,
              domain = domain+[('id', '!=', 316)],  # conflicts with 315
              include = ['state'])  # change to correct state
migrate_model('helpdesk.ticket', create = False, domain = domain)
migrate_model('helpdesk.ticket', domain = domain)
migrate_model('project.project', create = False,
              domain = domain, include = ['favorite_user_ids'])
migrate_model('project.project', domain = domain,
              exclude = ['rating_status', 'rating_status_period'])
migrate_model('project.task', create = False, domain = domain)
migrate_model('project.task', domain = domain)
for _id in sorted(source.env['mail.followers'].search([])):
    try:
        migrate_model('mail.followers', ids = [_id])
    except:
        continue


Webbplats
migrate_model('slide.channel', exclude = ['visibility'])
migrate_model('slide.slide', create = False)
migrate_model('slide.slide', exclude = ['message_follower_ids'])
create_new_webpages('website.page')
create_new_webpages('ir.ui.view', ids = [1640])  # Jobs
migrate_model('website.menu', exclude = ['page_id'])
migrate_model('website', create = False,
              include = ['name', 'social_github'])
# Conflicting file when changing theme
target.env['ir.attachment'].browse(2512).unlink()

create_new_webpages('ir.ui.view', ids = [('id', '=', 1624)])
create_new_webpages('ir.ui.view', ids = [('id', '=', 1640)])  # Lediga tjänster
create_new_webpages('ir.ui.view', ids = [('id', '=', 711)])  # Om oss
migrate_model('account.account')
migrate_model('account.bank.statement.cash
        filter(lambda x: type(x) is int, box')
migrate_model('account.invoice')
migrate_model('account.move.line')
migrate_model('account.tag')
migrate_model('board.board')
migrate_model('mail.message', include=[
              'author_avatar', 'author_id', 'date', 'message_type', 'message_id', 'model', 'res_id'])


MAIL.MESSAGE IN PROJECT.TASK
============================

model = 'project.task'
source_ids = sorted(source.env[model].search([]))
for source_id in source_ids:
    target_id = get_target_id_from_source_id(model, source_id)
    # target_message_ids = target.env[model].read(target_id)[0]['message_ids']
    # for target_message_id in target_message_ids:
    #     target.env['mail.message'].unlink(target_message_id)
    message_ids = sorted(source.env[model].read(source_id)[0]['message_ids'])
    for message_id in message_ids:
        migrate_model('mail.message', custom={
                      'res_id': target_id}, exclude=['tracking_value_ids'], ids=[message_id])
        tracking_value_ids = sorted(source.env['mail.message'].read(
            message_id)[0]['tracking_value_ids'])
        for tracking_value_id in tracking_value_ids:
            vals = source.env['mail.tracking.value'].read(tracking_value_id)
            field_name = vals[0]['field']
            field_id = target.env['ir.model.fields'].search(
                [('model', '=', model), ('name', '=', field_name)])[0]
            migrate_model('mail.tracking.value', custom={
                'field': field_id}, ids=[tracking_value_id])
    print(f"Recordset('{model}', [{source_id}]).message_ids DONE!")

"""
