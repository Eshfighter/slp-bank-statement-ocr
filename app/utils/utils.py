import os
import shutil
import yaml
import ruamel.yaml.util
import re


def clear_temp_files(path, file_index):
    folder_path = path
    for file_object in os.listdir(folder_path):
        if str(file_index) in file_object:
            file_object_path = os.path.join(folder_path, file_object)
            if os.path.isfile(file_object_path):
                os.unlink(file_object_path)
            else:
                shutil.rmtree(file_object_path) 


def load_config(bank_config):
    with open(bank_config, 'r', encoding='utf8') as stream:
        try:		
            config = ruamel.yaml.load(stream, ruamel.yaml.RoundTripLoader, preserve_quotes=True)
            fields_array = config
        except yaml.YAMLError as exc:
            print(exc)
    
    stream.close()
    return fields_array


def regex_lookup(regex_list, input_item):
    for i, match in enumerate(regex_list):
        if re.findall(match, str(input_item)) and not ('INV' in str(input_item)):
            return True
    return False


def find_month_text(input_item):
    month_list = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    for month in month_list:
        if month in input_item:
            return True
    return False


def convert(name):
    under_pat = re.compile(r'-([a-z])')
    return under_pat.sub(lambda x: x.group(1).upper(), name)


def convertJSON(j):
    out = {}
    for k in j:
        newK = convert(k)
        if isinstance(j[k], dict):
            out[newK] = convertJSON(j[k])
        elif isinstance(j[k], list):
            out[newK] = convertArray(j[k])
        else:
            out[newK] = j[k]
    return out


def convertArray(a):
    newArr = []
    for i in a:
        if isinstance(i, list):
            newArr.append(convertArray(i))
        elif isinstance(i, dict):
            newArr.append(convertJSON(i))
        else:
            newArr.append(i)
    return newArr
