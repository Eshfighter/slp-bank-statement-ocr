#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import base64
from datetime import datetime

from app.process_extracted_data import process_extracted_data
from app.extract_data import extract_text_native, extract_text_scanned
from app.utils import utils
from random import randint
from app.routes import identify_format
import cv2


def start(payload=None):
    # Sanity check
    if not payload:
        return {'Error': 'null payload'}

    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    temp_dir = os.path.join(base_dir, 'assets', 'temp_file')

    # Create temp folder if it does not exist
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)

    file_index = randint(0, 100000000000)

    start_time = time.time()

    bank_name = payload["bankName"].lower().replace(' ', '_')
    topOrg = payload["topOrg"]
    req_file = payload["fileContent"]
    file_id = payload["fileId"]

    filename = 'temp_' + str(file_index) + '.pdf'
    file_path = os.path.join(temp_dir, filename)

    with open(file_path, 'wb') as pdf_file:
        pdf_file.write(base64.b64decode(req_file))

    # Identify bank statement format
    configuration_fields = identify_format.from_bank_name(bank_name, file_path, base_dir)
    if configuration_fields:
        print('[INFO] Detected Format: %s' % configuration_fields['init-config']['format-id'])

    try:
        # extract text for native
        pdf_extracted_text = extract_text_native.pdf_to_text(file_path)

        # extract text from pdf
        if len(pdf_extracted_text) > 0:
            print('[INFO] PDF Type: Native')
            pdfcheck = "PDF - Native"

            # Get summary lines if applicable
            summary_lines = None
            if 'summary-page-index' in configuration_fields['summary-config']:
                summary_lines = extract_text_native.pdf_to_text_summary_page(file_path, configuration_fields['summary-config']['summary-page-index'])

            # Check for scanned summary if applicable
            if 'summary-scanned' in configuration_fields['summary-config'] and configuration_fields['summary-config']['summary-scanned'] is True:
                present_page_numbers = []
                for page_output in pdf_extracted_text['page-output']:
                    present_page_numbers.append(page_output[0]['page-number'])

                if len(present_page_numbers) == pdf_extracted_text['number-of-pages']:
                    summary_lines = extract_text_native.pdf_to_text_summary_page(file_path, configuration_fields['summary-config']['summary-page-index'])
                else:
                    updated_page_output = []
                    for i in range(1, pdf_extracted_text['number-of-pages'] + 1):
                        if i not in present_page_numbers:
                            scanned_page_text = extract_text_scanned.run_single(file_path, temp_dir, configuration_fields, i)
                            updated_page_output.append(scanned_page_text)
                            input_img = cv2.imread(scanned_page_text[0]['filename'])

                            cropped_summary_areas = configuration_fields['cropped-summary-areas']
                            for key in cropped_summary_areas:
                                extracted_text = extract_text_scanned.extract_summary_field(cropped_summary_areas[key],
                                                                                            input_img)
                                summary_lines = extracted_text.split(',')

                                # Minor cleanup
                                cleaned_summary_lines = []
                                for i, summary_line in enumerate(summary_lines):
                                    if i == 0 or i == 1:
                                        line_first_word = summary_line.strip().split(' ')[0]
                                        if not line_first_word.isdigit() and not line_first_word.isupper():
                                            continue

                                    if len(summary_line.strip()) > 2:
                                        cleaned_summary_lines.append(summary_line.strip())
                                summary_lines = cleaned_summary_lines
                        else:
                            index = present_page_numbers.index(i)
                            updated_page_output.append(pdf_extracted_text['page-output'][index])

                    pdf_extracted_text['page-output'] = updated_page_output

            text_extracted_list = pdf_extracted_text["page-output"]

            extracted_table = None
            if 'new-pipeline' in configuration_fields['init-config'] and configuration_fields['init-config']['new-pipeline'] is True:
                # Extract pdf table
                table_settings = {
                    'horizontal_strategy': configuration_fields['init-config']['horizontal-strategy'],
                    'vertical_strategy': configuration_fields['init-config']['vertical-strategy']
                }
                new_pipeline_keywords = None
                if 'new-pipeline-key-words' in configuration_fields['init-config']:
                    new_pipeline_keywords = configuration_fields['init-config']['new-pipeline-key-words']

                extracted_table = extract_text_native.pdf_to_text_table(file_path, configuration_fields, table_settings, keywords=new_pipeline_keywords)

            final_result = process_extracted_data.process_text(text_extracted_list, configuration_fields, pdfcheck, extracted_table=extracted_table, summary_lines=summary_lines)
        else:
            print('[INFO] PDF Type: Scanned Copy')
            pdfcheck = "PDF - Scanned Copy"

            # Handle summary if applicable
            summary_lines = None
            if 'cropped-summary-areas' in configuration_fields:
                cropped_summary_areas = configuration_fields['cropped-summary-areas']
            else:
                cropped_summary_areas = None

            if cropped_summary_areas is not None and 'crop-account-name-address-area' in cropped_summary_areas:
                if 'summary-page-index' in configuration_fields['summary-config']:
                    scanned_page_text = extract_text_scanned.run_single(file_path, temp_dir, configuration_fields, configuration_fields['summary-config']['summary-page-index'] + 1)
                    input_img = cv2.imread(scanned_page_text[0]['filename'])

                    extracted_text = extract_text_scanned.extract_summary_field(cropped_summary_areas['crop-account-name-address-area'],
                                                                                input_img)
                    summary_lines = extracted_text.split(',')

                    # Minor cleanup if applicable
                    if 'account-no-address' not in configuration_fields['summary-config']:
                        cleaned_summary_lines = []
                        stop = False
                        for i, summary_line in enumerate(summary_lines):
                            if stop:
                                break

                            if i == 0 or i == 1:
                                line_first_word = summary_line.strip().split(' ')[0]
                                if not line_first_word.isdigit() and not line_first_word.isupper():
                                    continue

                            if '  ' in summary_line:
                                summary_line_split = summary_line.split('  ')
                                summary_line_split = [item for item in summary_line_split if len(item) > 0]
                                if len(summary_line_split) == 2:
                                    summary_line = summary_line_split[1].strip()

                            if 'SINGAPORE ' in summary_line:
                                stop = True

                            cleaned_line = ''
                            for word in summary_line.split(' '):
                                if len(word) == 1 and not word.isdigit():
                                    continue

                                if '--' in word or '——' in word:
                                    continue

                                cleaned_line += word + ' '

                            if len(cleaned_line.strip()) > 2:
                                cleaned_summary_lines.append(cleaned_line.strip())
                        summary_lines = cleaned_summary_lines

            text_list = extract_text_scanned.run(file_path, temp_dir, configuration_fields)
            final_result = process_extracted_data.process_text(text_list, configuration_fields, pdfcheck, summary_lines=summary_lines)

        final_result = utils.convertJSON(final_result)
        final_result['fileId'] = file_id
        final_result['topOrg'] = topOrg
        print('[INFO] topOrg: %s' % topOrg)
    except Exception as e:
        print("[ERROR] Exception: %s" % e)
        final_result = {
            'fileId': file_id,
            'topOrg': topOrg,
            'statementResults': []
        }

    # delete all files saved
    utils.clear_temp_files(temp_dir, file_index)

    # debug logging
    processing_duration = time.time() - start_time
    total_pages = 0
    for result in final_result['statementResults']:
        total_pages += result['summary']['numberOfPages']

    print("[INFO] Total processing duration: %.02f seconds" % processing_duration)
    if total_pages > 0:
        print('[INFO] Processing time per page: %.02f seconds' % (processing_duration/total_pages))
    print('[INFO] Current time: ' + str(datetime.now()))
    return final_result
