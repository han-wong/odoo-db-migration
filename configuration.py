#!/usr/bin/env python3
import odoorpc
from termcolor import colored, cprint
import http.client as http
http.HTTPConnection._http_vsn = 10
http.HTTPConnection._http_vsn_str = 'HTTP/1.0'


# from credentials import *
source = odoorpc.ODOO.load('source')
target = odoorpc.ODOO.load('target')
source.env.context['active_test'] = False
target.env.context['active_test'] = False

txt_d = colored('DEBUG: MODEL', 'white', 'on_green')
txt_e = colored('ERROR:', 'yellow')
txt_i = colored('INFO:', 'green')
IMPORT_MODULE_STRING = '__import__'

print(f"{txt_i} source.env\n{source.env}")
print(f"{txt_i} source.host\n{source.host}")
print(f"{txt_i} source.db.list()\n{source.db.list()}\n")
print(f"{txt_i} target.env\n{target.env}")
print(f"{txt_i} target.host\n{target.host}")
print(f"{txt_i} target.db.list()\n{target.db.list()}\n")

''' Glossary
domain = list of search criterias
fields = what you get from source.env[model].read(id, [keys])
    id = number
   ids = what you get from source.env[model].search([])
 model = ex. 'res.partner'
     r = record, what you get from source.env[model].browse(id)
    rs = recordset, what you get from source.env[model].browse(ids)
source = source database
target = target database
'''

# HELPER FUNCTIONS


def unlink(model, only_migrated=True):
    ''' unlinks all records of a model in target database
    example: unlink('res.partner')
    '''
    record_list = []
    if only_migrated:
        domain = [('module', '=', IMPORT_MODULE_STRING), ('model', '=', model)]
        data_ids = target.env['ir.model.data'].search(domain)
        data_recordset = target.env['ir.model.data'].browse(data_ids)
        for record in data_recordset:
            record_list.append(record.res_id)
    else:
        record_list = target.env[model].search([])

    try:
        target.env[model].browse(record_list).unlink()
        print(
            f"{txt_i} Recordset('{model}', {record_list}) unlinked"
        )
    except Exception as e:
        print(e)


def create_xmlid(model, target_record_id, source_record_id):
    ''' Creates an external id for a model
    example: create_xml_id('product.template', 89122, 5021)
    '''

    xml_id = f"{IMPORT_MODULE_STRING}.{model.replace('.', '_')}_{source_record_id}"
    values = {
        'module': xml_id.split('.')[0],
        'name': xml_id.split('.')[1],
        'model': model,
        'res_id': target_record_id,
    }
    try:
        target.env['ir.model.data'].create(values)
        print(f"{txt_i} TARGET: XML_ID: {xml_id} | CREATE: SUCCESS!")
    except:
        print(
            f"{txt_e} TARGET: XML_ID: {xml_id} | CREATE: FAIL! Should not happen...Did you call this method manually?"
        )


def get_target_id_from_source_id(model, source_id):
    '''
    Returns id from target using id from source
    Ex, get_target_id_from_source_id('product.attribute', 3422)
    Returns: False if record cannot be found
    '''
    xmlid = f"{IMPORT_MODULE_STRING}.{model.replace('.', '_')}_{source_id}"
    return target.env['ir.model.data'].xmlid_to_res_id(xmlid)


def get_target_id_from_source_xmlid(model, source_id):
    '''
    Returns id from target using source xmlid
    Ex, get_target_id_from_source_xmlid('res.company', 1)
    Returns: False if record cannot be found
    '''
    domain = [('model', '=', model), ('res_id', '=', source_id)]
    r_id = source.env['ir.model.data'].search(domain, limit=1)
    if r_id:
        key = 'complete_name'
        data = source.env['ir.model.data'].read(r_id, [key])[0]
        xmlid = data.get(key, None)
        if xmlid:
            target_id = target.env['ir.model.data'].xmlid_to_res_id(xmlid)
            if target_id:
                return target_id
    return False


def create_record_and_xmlid(model, model2, fields, source_id):
    '''
    Creates record on target if it doesn't exist, using fields as values,
    and creates an external id so that the record will not be duplicated if function is called next time

    Example: create_record_and_xml_id('res.partner', {'name':'MyPartner'}, 2)

    Returns 0 if function fails
    '''
    target_id = get_target_id_from_source_id(model2, source_id)
    if target_id:
        print(f"{txt_i} External id already exist ({model2} {source_id})")
    else:
        try:
            target_id = target.env[model2].create(fields)
            print(f"{txt_i} SOURCE: {model} {source_id} | TARGET: {model2} {target_id} | CREATE: SUCCESS! Creating external id...")
            create_xmlid(model2, target_id, source_id)
            return target_id
        except Exception as e:
            print(
                f"{txt_e} SOURCE: {model} {source_id} | TARGET: {model2} {target_id} | CREATE: FAIL! Read the log...")
            print(e)
            return 0


def migrate_model(model, **vars):
    '''
    Use this method for migrating model from source to target
    - Example: migrate_model('res.partner')
    - Keyworded arguments default values:

    Parameters
        - model (str) - Model to migrate records from source to target
        - **vars : keyworded arguments
            - calc    (dict) - Runs code on specific fields, default {}
            - context (dict) - Sets context to source and target, default {}
            - create  (bool) - Creates records, set to False to update records, default True
            - custom  (dict) - Updates vals before create/write, default {}
            - debug   (bool) - Shows debug messages, default False
            - depth   (int)  - Recursively creates missing records in many2one fields if set higher than 0, default 0
            - domain  (list) - Migrate records that matches search criteria, i.e [('name','=','My Company')], default []
            - diff    (dict) - If field names don't match in source and target i.e {'image':'image_1920'}, default {}
            - exclude (list) - Excludes certain fields in source i.e ['email_formatted'], default []
            - ids     (list) - Provide your own record ids to migrate i.e [1,3], default []
            - include (list) - Provide your own list of fields names to migrate ['name','email'], default []
            - model2  (str)  - Migrate records to another model, default same as model

    Returns
        - vals (dict) if create/write fails
        - id   (int)  if create succeeds
    '''
    calc = vars.get('calc', {})
    command = vars.get('command', {})
    context = vars.get('context', {})
    create = vars.get('create', True)
    custom = vars.get('custom', {})
    debug = vars.get('debug', False)
    depth = vars.pop('depth', 0)
    domain = vars.get('domain', [])
    ids = vars.get('ids', [])
    model2 = vars.get('model2', model)
    source.env.context.update(context)
    target.env.context.update(context)

    if debug:
        print(f"{txt_d} source context:{source.env.context}")
        print(f"{txt_d} target context:{target.env.context}")
        print(f"{txt_d} model:{model}")
        print(f"{txt_d} vars:{vars}")

    source_model = source.env[model]
    source_fields = source_model.fields_get()
    target_model = target.env[model2]
    target_fields = target_model.fields_get()
    common_fields = get_common_fields(source_fields, target_fields, **vars)
    source_ids = ids if ids else sorted(source_model.search(domain))
    if not source_ids:
        f"{txt_i} No records to migrate..."
    for source_id in source_ids:
        print(f"{txt_d} {model} {source_id}") if debug else None

        target_record = get_target_id_from_source_id(model2, source_id)
        if debug:
            print(f"{txt_d} target_record{target_record} {model2}")

        if not target_record:
            if debug:
                print(
                    f"{txt_d} No record found with __import__.{model2.replace('.', '_')}_{source_id} external identifier")
            target_record = get_target_id_from_source_xmlid(model2, source_id)

        if create and target_record:
            print(
                f"{txt_i} SOURCE: {model} {source_id} | TARGET: {model2} {target_record} | CREATE: FAIL! External id exists..."
            )
            continue

        if not create and not target_record:
            print(
                f"{txt_i} SOURCE: {model} {source_id} | TARGET: {model2} {target_record} | WRITE: FAIL! External id exists..."
            )
            continue
        vals = {}
        try:
            source_record = source_model.read(source_id, list(common_fields))
        except:
            print(
                f"{txt_e} SOURCE: {model} {source_id} READ: FAIL! Does the record exist?")
            if debug:
                return source_id
            continue

        # Customize certain fields before creating records
        for key in common_fields:
            if not calc or key not in calc.keys():
                key_type = source_fields[key]['type']

                if debug:
                    print(f"{txt_d} {key} {key_type}")

                if key_type == 'many2one':
                    if not source_record[key]:
                        continue
                    relation = key_type = source_fields[key]['relation']

                    if debug:
                        print(f"{txt_d} {key} {relation}")

                    relation_id = get_target_id_from_source_id(
                        relation, source_record[key][0])
                    if not relation_id:
                        relation_id = get_target_id_from_source_xmlid(
                            relation, source_record[key][0])
                    if not relation_id and depth:
                        relation_id = migrate_model(
                            relation, depth=depth-1, **vars)
                    if type(relation_id) is dict or not relation_id:
                        continue
                    vals.update({common_fields[key]: relation_id})

                elif key_type == 'many2many':
                    if not source_record[key]:
                        continue
                    relation = key_type = source_fields[key]['relation']

                    if debug:
                        print(f"{txt_d} {key} {relation}")

                    key_ids = []
                    values = 0
                    for many_id in source_record[key]:
                        relation_id = get_target_id_from_source_id(
                            relation, many_id)
                        if not relation_id:
                            relation_id = get_target_id_from_source_xmlid(
                                relation, many_id)
                        if not relation_id:
                            continue
                        key_ids.append(relation_id)
                    if command and key in command:
                        if command[key] == 6:
                            values = [6, 0]
                            values.append(key_ids)
                            values = [tuple(values)]
                    else:
                        values = key_ids
                    vals.update({common_fields[key]: values})

                elif key_type == 'one2many':
                    if not source_record[key]:
                        continue
                    relation = key_type = source_fields[key]['relation']

                    if debug:
                        print(f"{txt_d} {key} {relation}")

                    key_ids = []
                    values = 0
                    for many_id in source_record[key]:
                        relation_id = get_target_id_from_source_id(
                            relation, many_id)
                        if not relation_id:
                            relation_id = get_target_id_from_source_xmlid(
                                relation, many_id)
                        if not relation_id:
                            continue
                        key_ids.append(relation_id)
                    if command and key in command:
                        if command[key] == 4:
                            values = [tuple([4, key_ids[0], 0])]
                        if command[key] == 6:
                            values = [tuple([6, 0, key_ids])]
                    else:
                        values = key_ids
                    vals.update({common_fields[key]: values})

                elif key_type == 'integer':
                    if key == 'res_id' and 'res_model' in source_record:
                        res_model = source_record['res_model']
                        if not res_model:
                            continue
                        res_id = get_target_id_from_source_id(
                            res_model, source_record[key])
                        if not res_id:
                            res_id = get_target_id_from_source_xmlid(
                                res_model, source_record[key])
                        if not res_id:
                            continue
                        else:
                            vals.update({common_fields[key]: res_id})
                            continue
                    vals.update({common_fields[key]: source_record[key]})

                elif key_type == 'char':
                    val = source_record[key]
                    if key == 'arch':
                        val = update_images(source_record[key])

                    # Remove /page if it exists in url (odoo v8 -> odoo 14)
                    elif key == 'url' and type(source_record[key]) is str:
                        val = source_record[key]
                        if val.startswith('/page'):
                            val = val.replace('/page', '')

                    vals.update({common_fields[key]: val})

                elif key_type in ['binary', 'boolean', 'date', 'datetime', 'float', 'selection']:
                    vals.update({common_fields[key]: source_record[key]})
                # else:
                #     vals.update({common_fields[key]: source_record[key]})

        vals.update(custom)

        if calc:
            for key in calc.keys():
                exec(calc[key])

        # Break operation and return last dict used for creating record if something is wrong and debug is True
        if create:
            create_id = create_record_and_xmlid(
                model, model2, vals, source_id)
            if not create_id:
                return vals
            elif ids and len(ids) == 1:
                return create_id
        elif target_record:
            try:
                success = target_model.browse(target_record).write(vals)
                if success:
                    print(
                        f"{txt_i} SOURCE: {model} {source_id} TARGET: {model2} {target_record} WRITE: SUCCESS!!!"
                    )
                else:
                    print(target_record)
                    return vals
            except:
                print(
                    f"{txt_e} SOURCE: {model} {source_id} TARGET: {model2} {target_record} WRITE: FAIL!"
                )
                return vals

    for key in context: 
        source.env.context.pop(key)
        target.env.context.pop(key)
        
    print(txt_i, f"Done!")


def get_common_fields(source_fields, target_fields, **vars):
    '''
    Returns dict with key as source model keys and value as target model keys

    Use exclude = ['this_field', 'that_field'] to exclude keys on source model

    Use diff = {'image':'image_1920'} to update key-value pairs manually
    '''
    diff = vars.get('diff', {})
    exclude = vars.get('exclude', [])
    include = vars.get('include', [])
    fields = {}

    for key in source_fields:
        if include:
            if key in include and key in target_fields:
                fields.update({key: key})
        elif exclude and key in exclude:
            continue
        else:
            if key in target_fields:
                fields.update({key: key})

    fields.update(diff)

    return fields


def get_all_fields(model, exclude=[], diff={}):
    '''
    Returns dict with key as source model keys and value as target model keys

    Use exclude = ['this_field', 'that_field'] to exclude keys on source model

    Use diff = {'image':'image_1920'} to update key-value pairs manually
    '''
    fields = {}
    target_field_keys = target.env[model]._columns

    for key in source.env[model]._columns:
        if key in exclude:
            continue
        elif key in target_field_keys:
            fields.update({key: key})

    fields.update(diff)

    return fields


def get_fields_difference(model):
    '''
    Returns list with fields difference

    Example: get_fields_difference('res.company')
    '''
    source_set = set(source.env[model]._columns)
    target_set = set(target.env[model]._columns)

    return {
        'source': source_set - target_set,
        'target': target_set - source_set
    }


def get_required_fields(model):
    '''
    Returns list with required fields

    Example: get_required_fields('res.company')
    '''
    source_dict = source.env[model].fields_get()
    target_dict = target.env[model].fields_get()
    source_keys = []
    target_keys = []
    for key in source_dict:
        if source_dict[key]['required']:
            source_keys.append(key)
    for key in target_dict:
        if target_dict[key]['required']:
            target_keys.append(key)
    return {'source': source_keys, 'target': target_keys}


def print_relation_fields(model, model2=''):
    '''Prints model name for relation fields'''
    source_fields = source.env[model].fields_get()
    target_fields = target.env[model2 or model].fields_get()
    print('source')
    for key in sorted(source_fields):
        if source_fields[key].get('relation', None):
            relation = source_fields[key]['relation']
            key_type = source_fields[key]['type']
            text = 'relation: {:<30} type: {:<10} key: {:<30}'
            print(text.format(relation, key_type, key))
    input(f"{txt_i} Press a key to continue")
    print('target')
    for key in sorted(target_fields):
        if target_fields[key].get('relation', None):
            relation = target_fields[key]['relation']
            key_type = target_fields[key]['type']
            text = 'relation: {:<30} type: {:<10} key: {:<30}'
            print(text.format(relation, key_type, key))
    input(f"{txt_i} The end")


def print_list(my_list, rows=40):
    from pprint import pprint
    count = len(my_list)
    begin = 0
    end = rows
    for x in range(int(count/rows)):
        pprint(my_list[begin:end])
        begin = end
        end = end + rows
        input()


def compare_records(model, source_id, key_len=150, rows=14):
    source_fields = source.env[model].fields_get()
    target_fields = target.env[model].fields_get()
    keys = sorted(set(list(source_fields)+list(target_fields)))
    count = 1
    target_id = get_target_id_from_source_id(model, source_id)
    if not target_id:
        target_id = get_target_id_from_source_xmlid(model, source_id)
    for key in keys:
        source_val = source_rel = source_type = ''
        target_val = target_rel = target_type = ''
        if count % rows == 1:
            print(
                f"{'field name':^40}{'source type':^20}{'source model':^20}{'target type':^20}{'target model':^20}")
        if key in source_fields:
            source_type = source_fields[key]['type']
            if source_type in ['many2many', 'many2one', 'one2many']:
                source_rel = source_fields[key]['relation']
            try:
                source_val = str(source.env[model].read(source_id, [key])[
                    0].get(key, 'Key not found'))[:key_len]
            except:
                source_val = 'error'

        if key in target_fields:
            target_type = target_fields[key]['type']
            if target_type in ['many2many', 'many2one', 'one2many']:
                target_rel = target_fields[key]['relation']
            try:
                target_val = str(target.env[model].read(target_id, [key])[
                    0].get(key, 'Key not found'))[:key_len]
            except:
                target_val = 'error'

        print(f"""{key:^40}{source_type:^20}{source_rel:^20}{target_type:^20}{target_rel:^20}
S {source_val}
T {target_val}""")
        if count % rows == 0:
            input()
        count = count+1


def create_new_webpages(model, ids=[]):
    ''' Creates new website pages on target using source pages' arch
    '''
    if not ids:
        ids = sorted(source.env[model].search([]))
    for _ in ids:
        source_val = source.env[model].read(_)[0]
        source_arch = update_images(source_val['arch'])
        source_id = source_val['id']
        source_name = source_val['name']
        target_id = get_target_id_from_source_id(
            'website_page', source_val['id'])
        if target_id:
            print(
                f"{txt_i} SOURCE: {model} {source_id} | TARGET: {model} {target_id} | CREATE: FAIL! External id exists...")
            continue
        new_page = target.env['website'].new_page(name=source_name)
        create_xmlid(model, new_page['view_id'], source_id)
        new_record = target.env['ir.ui.view'].browse(new_page['view_id'])
        new_record.arch = source_arch
        print(
            f"INFO: Created new [{model}] and external id from source id [{source_id}] [{source_name}]")
        print('=================================================================================================')
    print(colored('DONE:', 'green'))


def update_images(arch):
    from bs4 import BeautifulSoup
    model = 'ir.attachment'
    soup = BeautifulSoup(arch, 'html.parser')
    tag_list = ['div', 'img', 'span']
    tags = soup.find_all(tag_list)

    for tag in tags:
        attr = t = url = ''
        at = 'access_token'
        if tag.name == 'img' and tag.has_attr('src'):
            attr = 'src'
        elif tag.name in ['div', 'span'] and tag.has_attr('style'):
            attr = 'style'
        if attr:
            url = tag[attr].split('/')
        if attr and url and 'web' in url and 'image' in url:
            i = url.index('image')+1
            source_id = target_id = 0
            t = ''
            if url[i].isdigit():
                source_id = int(url[i])
            elif at in url[i]:
                url_split = url[i].split('?')
                source_id = url_split[0]
                t = url_split[1]
                if source_id.isdigit():
                    source_id = int(source_id)
            else:
                pass

            if source_id:
                target_id = get_target_id_from_source_id(model, source_id)
                # if source_id exists but cannot find in target, try migrating it, doing it manually takes too much time
                if not target_id:
                    try:
                        migrate_model(model, ids=[source_id])
                    except:
                        print(f"{txt_e} {source_id}")
            if target_id:
                url[i] = str(target_id)
                if t:
                    t = target.env[model].read(target_id, [at])[0][at]
                    url[i] += f"?{at}={t}"

            tag[attr] = '/'.join(url)

    return str(soup)


print(f"{txt_i} functions loaded")

'''
model = 'mail.activity'
one=0
domain=[]
include=[]
exclude = []
diff = {}
model2 = model
source_model = source.env[model]
source_fields = source_model.fields_get()
target_model = target.env[model2]
target_fields = target_model.fields_get()
common_fields = get_common_fields(
    source_fields, target_fields, include=include, exclude=exclude, diff=diff)
source_ids = one if one else sorted(
    filter(lambda x: type(x) is int, source_model.search(domain)))
source_id = 66
new_record = {}
target_record = get_target_id_from_source_xmlid(model, source_id)
source_record = source_model.read(source_id, list(common_fields))[0]
key = 'message_id'
key_type = source_fields[key]['type']

model='project.task.type'
for x in sorted(source.env[model].search([])):
    print(x, source.env[model].browse(x).name)
    if x % 10 == 0:
        input()
for x in sorted(target.env[model].search([])):
    print(x, target.env[model].browse(x).name)
    if x % 10 == 0:
        input()

model='sale.report'
print('source')
for x,y in source.env[model].fields_get().items():
    if y.get('relation',None):
        print('key: {:<25} relation: {:<25}'.format(x,y['relation']))
print('target')
for x,y in target.env[model].fields_get().items():
    if y.get('relation',None):
        print('key: {:<25} relation: {:<25}'.format(x,y['relation']))
'''
