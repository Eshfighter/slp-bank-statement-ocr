# -*- coding: utf-8 -*-
import pytesseract as pt
import re
from app.utils import utils

config = "-l eng --oem 1 --psm 6 --dpi 150 -c preserve_interword_spaces=1 OMP_THREAD_LIMIT=1 --tessdata-dir app/assets/tesseract_traineddata"
config_line = "-l digitsall_layer --oem 1 --psm 7 --dpi 150 -c OMP_THREAD_LIMIT=1 --tessdata-dir app/assets/tesseract_traineddata"
config_box = "-l digitsall_layer --oem 1 --psm 8 --dpi 150 -c OMP_THREAD_LIMIT=1 --tessdata-dir app/assets/tesseract_traineddata"


def convert_image_to_string(img):
    result = pt.image_to_string(img, config=config)
    return result


def convert_image_to_data(img, filename, page_number, bank_name, regex_list):
    print('--- Processing page %d ---' % page_number)
    output = pt.image_to_data(img, config=config, output_type=pt.Output.DICT)
    line_num = 0
    text_list = []
    left = 0
    width = 0
    amount_found = False
    height_img, width_img = img.shape
    for i, level in enumerate(output['level']):
        text_result = {}
        if level == 5:
            number_match = utils.regex_lookup(regex_list, output['text'][i])
            if bank_name != 'CIMB':
                cents_match = re.match(
                    r'(\.|\-)?(\d|[O]|[o]|[s]|[$]|[S]|[§])?(\d|[O]|[o]|[s]|[$]|[S]|[§])(\d|[O]|[o]|[s]|[$]|[S]|[§])(\.|\+|\-)?$',
                    output['text'][i])
            else:
                cents_match = False
            if output['line_num'][i] != line_num:
                if (len(text_list) > 0 and 'txn-balance-coordinate' not in text_list[-1] and 'txn-amt-coordinate' in
                        text_list[-1] and text_list[-1]['txn-amt-coordinate'][2] < (0.7 * width_img)):
                    try:
                        amt_coordinate = text_list[-1]['txn-amt-coordinate']
                        text_list[-1]['txn-balance-coordinate'] = []
                        text_list[-1]['txn-balance-coordinate'].append(amt_coordinate[0])
                        text_list[-1]['txn-balance-coordinate'].append(amt_coordinate[1])
                        text_list[-1]['txn-balance-coordinate'].append(amt_coordinate[2] + 100)
                        text_list[-1]['txn-balance-coordinate'].append(width_img - 10)
                    except:
                        text_list[-1]['txn-balance-coordinate'] = []
                text_result['top'] = (output['top'][i] / height_img)
                text_result['text'] = output['text'][i]
                text_result['height'] = (output['height'][i] / height_img)
                text_result['position'] = {
                    'top': (output['top'][i] / height_img),
                    'height': (output['height'][i] / height_img),
                    'start-left': output['left'][i] / width_img
                }
                text_result['filename'] = filename
                text_result['page-number'] = page_number
                line_num = output['line_num'][i]
                amount_found = False
                word_count = 1
                text_list.append(text_result)
            else:
                if output['left'][i] - width - left < 30:
                    text_list[-1]['text'] = " ".join([text_list[-1]['text'], output['text'][i]])
                    if 'txn-amt-coordinate' in text_list[-1] and 'txn-balance-coordinate' not in text_list[-1]:
                        text_list[-1]['txn-amt-coordinate'][3] = text_list[-1]['txn-amt-coordinate'][3] + \
                                                                 output['width'][i] + 5
                    elif 'txn-balance-coordinate' in text_list[-1]:
                        text_list[-1]['txn-balance-coordinate'][3] = text_list[-1]['txn-balance-coordinate'][3] + \
                                                                     output['width'][i] + 5
                else:
                    text_list[-1]['text'] = "  ".join([text_list[-1]['text'], output['text'][i]])
                    if 'txn-amt-coordinate' not in text_list[-1] and 'txn-balance-coordinate' not in text_list[-1]:
                        text_list[-1]['position']['left' + str(word_count)] = output['left'][i] / width_img
                        word_count += 1
            if amount_found and 'txn-balance-coordinate' not in text_list[-1] and (number_match or cents_match):
                text_list[-1]['txn-balance-coordinate'] = [output['top'][i] - 5,
                                                           output['top'][i] + output['height'][i] + 5,
                                                           output['left'][i] - 20,
                                                           output['left'][i] + output['width'][i] + 40]
            if (number_match or cents_match) and not amount_found and output['left'][i] > 0.25 * width_img:
                text_list[-1]['txn-amt-coordinate'] = [output['top'][i] - 5, output['top'][i] + output['height'][i] + 5,
                                                       output['left'][i] - 10,
                                                       output['left'][i] + output['width'][i] + 5]
                amount_found = True
            left = output['left'][i]
            width = output['width'][i]

    return text_list


def convert_image_to_string_number(img, segment):
    result = ''
    if segment == 'box':
        result = pt.image_to_string(img, config=config_box)
    elif segment == 'line':
        result = pt.image_to_string(img, config=config_line)
    return result
