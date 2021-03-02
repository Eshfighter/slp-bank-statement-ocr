import os
from app.utils import utils
from app.extract_data import extract_text_native, extract_text_scanned


def from_bank_name(bank_name, pdf_file_path, base_path):
    # Load all available formats
    config_dir = os.path.join(base_path, 'assets', 'bank_configurations')
    bank_configs = []
    summary_page_native = extract_text_native.pdf_to_text_summary_page(pdf_file_path)

    for config_file_name in os.listdir(config_dir):
        if config_file_name.endswith('.yml'):
            config_fields = utils.load_config(os.path.join(config_dir, config_file_name))
            bank_configs.append(config_fields)

    if bank_name == 'public_bank':
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'public_bank_my'][0]
    elif bank_name == 'ocbc':
        # TODO update when new formats come in
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'ocbc_sg_2'][0]
    elif bank_name == 'dbs':
        # TODO update when new formats come in
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'dbs_sg_1'][0]
    elif bank_name == 'scb':
        # TODO update when new formats come in
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'scb_sg_1'][0]
    elif bank_name == 'cimb':
        # Check if native text exists
        if len(summary_page_native) > 1:
            return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'cimb_my_native'][0]
        else:
            return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'cimb_my_scanned'][0]
    elif bank_name == 'maybank' or bank_name == 'ambank' or bank_name == 'rhb' or bank_name == 'uob':
        current_bank_configs = [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'].startswith(bank_name)]
        if len(summary_page_native) > 10:
            # Native
            summary_page_lines = summary_page_native
        else:
            # Scanned
            summary_page_scanned = extract_text_scanned.scanned_page_to_text_summary(pdf_file_path, 1)
            summary_page_lines = summary_page_scanned.split('\n')

        for current_bank_config in current_bank_configs:
            for summary_page_line in summary_page_lines:
                if current_bank_config['init-config']['format-key-word'] in summary_page_line:
                    return current_bank_config
    elif bank_name == 'alliance_bank':
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'alliance_bank_my_1'][0]
    elif bank_name == 'hlb':
        return [config_fields for config_fields in bank_configs if config_fields['init-config']['format-id'] == 'hlb_my_1'][0]

    return None


