# -*- coding: utf-8 -*-
import multiprocessing
import cv2
import os
import pdf2image
from functools import partial
import re
from app.extract_data import tesseract_ocr


def run(file_path, save_dir, configuration_fields):
    print("[INFO] OCR start")
    images_from_path = pdf2image.convert_from_path(file_path, first_page=0, last_page=0)
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    print('--- Temp file: %s ---' % base_filename)

    img_file_list = []

    print('--- Total Number of pages: %d ---' % len(images_from_path))
    for i, page in enumerate(images_from_path):
        new_filename = os.path.join(save_dir, base_filename) + '_' + str(i) + '.png'
        page.save(new_filename, 'PNG')
        img_file_list.append({'page-number': i+1, 'file-name': new_filename})
    
    pool = multiprocessing.Pool(4)
    return_list = pool.map(partial(extract_data, configuration_fields=configuration_fields), img_file_list,)
    pool.close()
    pool.join()

    print('[INFO] OCR end')

    return return_list


def run_single(file_path, save_dir, configuration_fields, page_number):
    images_from_path = pdf2image.convert_from_path(file_path, first_page=page_number, last_page=page_number)
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    page = images_from_path[0]
    new_filename = os.path.join(save_dir, base_filename) + '_' + str(page_number) + '.png'
    page.save(new_filename, 'PNG')
    img_file = {
        'page-number': page_number, 'file-name': new_filename
    }
    result = extract_data(img_file, configuration_fields)
    return result


def scanned_page_to_text_summary(file_path, page_number):
    images_from_path = pdf2image.convert_from_path(file_path, first_page=page_number, last_page=page_number)
    page = images_from_path[0]
    return tesseract_ocr.convert_image_to_string(page)


def extract_data(img_file, configuration_fields):
    img = cv2.imread(img_file['file-name'], 0)
    extracted_result = tesseract_ocr.convert_image_to_data(img, img_file['file-name'], img_file['page-number'],
                                                           configuration_fields['init-config']['bank-name'],
                                                           configuration_fields['transaction-config']['number-regex-list'])
    return extracted_result


def extract_summary_field(cropped_summary_config, input_img):
    coordinates = cropped_summary_config['coordinates']
    label_found = False
    extracted_raw_text = tesseract_ocr.convert_image_to_string(input_img[coordinates[0]:coordinates[1],coordinates[2]:coordinates[3]])
    extracted_raw_text_list = extracted_raw_text.split('\n')
    extracted_raw_text_list = list(filter(None, extracted_raw_text_list)) 
    if 'index' in cropped_summary_config:
        extracted_raw_text_list = [value for value in extracted_raw_text_list if not re.match(r'\d\d\d$',value)]
        extracted_raw_text_list = extracted_raw_text_list[cropped_summary_config['index'][0]:cropped_summary_config['index'][1]]
    if 'label' in cropped_summary_config:
        for index,text in enumerate(extracted_raw_text_list):
            splitted_text_list = text.split('  ')
            splitted_text_list = list(filter(None, splitted_text_list))
            if 'start-line' in cropped_summary_config and 'no-of-lines' in cropped_summary_config:
                if cropped_summary_config['label'] in text:
                    line_after_label = cropped_summary_config['start-line']
                    label_found = True
                    text_required = ''
                    while line_after_label <= cropped_summary_config['no-of-lines']:
                        text_required = text_required + extracted_raw_text_list[index+line_after_label].strip()
                        line_after_label += 1
                    extracted_raw_text_list = [text_required]
            else:
                extracted_raw_text_list,label_found = handle_text_blob(extracted_raw_text_list,splitted_text_list,cropped_summary_config,index)
            if label_found:
                break
        if not label_found:
            extracted_raw_text_list = ['']
        
    extracted_text = ', '.join(extracted_raw_text_list)
    final_text = extracted_text.strip()
    return final_text


def handle_text_blob(extracted_raw_text_list, splitted_text_list, cropped_summary_config, index):
    label_found = False
    for i, text in enumerate(splitted_text_list):
        if cropped_summary_config['label'] in text:
            label_found = True
            if 'value-different-line-from-label' in cropped_summary_config and cropped_summary_config['value-different-line-from-label']:
                try:
                    extracted_raw_text_list = extracted_raw_text_list[index + cropped_summary_config['label-value-index'][0]].split('  ')
                    extracted_raw_text_list = list(filter(None, extracted_raw_text_list))
                    if len(extracted_raw_text_list) > cropped_summary_config['label-value-index'][1]:
                        extracted_raw_text_list = [extracted_raw_text_list[cropped_summary_config['label-value-index'][1]]]
                    else:
                        extracted_raw_text_list = [extracted_raw_text_list[cropped_summary_config['label-value-index'][1]-1]]
                except:
                    extracted_raw_text_list = ['']
            elif i < (len(splitted_text_list) - 1):
                summary_value_to_extract = splitted_text_list[i+1]
                extracted_raw_text_list = [summary_value_to_extract]
            else:
                extracted_raw_text_list = ['']
            break
    return extracted_raw_text_list, label_found
