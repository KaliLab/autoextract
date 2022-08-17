import os
import sys
import json
import logging
logging.basicConfig(filename='extract.log', level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s')
import argparse
import bluepyefe as bpefe


###### HELPER FUNCTIONS ######
def get_subdirectory_list(path_str):
    directory_walk = list(os.walk(path_str))  # list of all subdirectories + files under path_str
    directory_root_tuple = directory_walk[0]  # select only first directory, i.e the path_str root
    subdirectories = directory_root_tuple[1]  # (root, dirs, files) tuple -> select dirs (list)
    return subdirectories


def filter_measurements_by_protocol(measurement_dict, protocol_type):
    filtered_measurement_dict = {}
    for cell in measurement_dict:
        for measurement in measurement_dict[cell]:
            if measurement_dict[cell][measurement]['protocol_type'] == protocol_type:
                if cell not in filtered_measurement_dict:
                    filtered_measurement_dict[cell] = {}
                filtered_measurement_dict[cell][measurement] = measurement_dict[cell][measurement]
    return filtered_measurement_dict
##############################


# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-cp', '--config-path', type=str, help='Path to JSON file containing extraction config info')
parser.add_argument('-ip', '--input-path', type=str, help='Root path for elphys measurement files.')
parser.add_argument('-op', '--output-path', type=str, help='Directory where the extraction results should be saved.')
args = parser.parse_args()

# load config JSON containing feature extraction configuration info
logging.info("Read autoextract config JSON")
with open(args.config_path) as config_json:
    config = json.load(config_json)

# set up variables in which we will collect from the protocol.txts
protocol_types = set()  # as we iterate through cells and meaurements, unique protocol names will be collected here
measurement_dict = {}  # this contains protocol data for each cell, for each measurement
logging.info("Find unique protocols, collect protocol.txt data for each cell and each measurement")

# find and iterate through input directory (each subdirectory is a cell)
cell_directories = get_subdirectory_list(args.input_path)
for cell in cell_directories:
    measurement_dict[cell] = {}
    ton, toff = None, None

    # find and iterate through measurement files
    cell_directory_path = "{}/{}".format(args.input_path, cell)
    measurement_dirs = get_subdirectory_list(cell_directory_path)
    for measurement_dir in measurement_dirs:
        measurement_dir_path = "{}/{}".format(cell_directory_path, measurement_dir)
        _, _, files = list(os.walk(measurement_dir_path))[0]
        measurement_files = list(filter(lambda name: "protocol" and "._" not in name[:2], files))  # select only true measurement files

        # read protocol file
        try:
            with open(measurement_dir_path + '/protocol.txt') as protocol_file:
                protocol_file_content = [line.strip("\n") for line in
                                         protocol_file.readlines()]  # read protocol file content, strip newline characters
                filter_empty = filter(lambda line: line != "", protocol_file_content)
                protocol_file_content = list(filter_empty)
        except FileNotFoundError:
            logging.warning("Protocol file not found for measurement {}. Skipping measurement.".format(measurement_dir))
            continue

        try:
            missing_swps = []
            if len(protocol_file_content) == 5:  # when there is no missing sweep the last line is empty
                protocol_type, channel, sampling_rate, parameters, amplitudes = protocol_file_content
            else:
                protocol_type, channel, sampling_rate, parameters, amplitudes, missing_swps = protocol_file_content
        except ValueError as e:
            logging.error("Error thrown for cell {}, measurement {}. Traceback:".format(cell, measurement_dir), exc_info=True)

        # calculate BPE-compatible values
        dt = 1. / int(sampling_rate) * 1e3
        ton, delta_t, _ = [int(p) for p in parameters.split()]
        toff = ton + delta_t
        amplitudes = [int(a) / 1000 for a in amplitudes.split()]  # division by 1000 to convert from pA to nA

        # collect unique protocols for grouping later
        protocol_types.add(protocol_type)

        # select file containing the desired channel data as described in the protocol
        try:
            channel_meas_file = list(filter(lambda name: channel in name, measurement_files))[0]
        except IndexError:  # channel name might contain double digits in filename
            channel_name_double_digit = channel[:2] + '0' + channel[2:]
            channel_meas_file = list(filter(lambda name: channel_name_double_digit in name, measurement_files))[0]
        channel_meas_file, _, _ = channel_meas_file.partition(".")  # extract part before the file extension
        channel_meas_file = "{}/{}".format(measurement_dir, channel_meas_file)  # to help BPE find the data txt

        # process missing sweep indices
        if missing_swps:
            missing_swps_indices = list(map(lambda idx: int(idx) - 1, missing_swps.split()))  # format sweep indices
            missing_swps = [amplitudes[idx] for idx in missing_swps_indices]

        # check if correct number of sweeps
        with open("{}/{}.txt".format(cell_directory_path, channel_meas_file), "r") as channel_meas_file_object:
            channel_meas_file_content = channel_meas_file_object.readlines()
            num_columns = len(channel_meas_file_content[0].split("\t"))
            num_amplitudes = len(amplitudes)
            if num_columns != num_amplitudes:
                logging.warning("Number of columns in measurement file doesn't match number of amplitudes. " \
                                "Number of amplitudes: {}. Number of columns: {}. Skipping measurement."
                                .format(measurement_dir, num_amplitudes, num_columns))
                continue

        # collect protocol.txt data into measurement_dict
        measurement_dict[cell][measurement_dir] = {
            "protocol_type": protocol_type,
            "measurement_file": channel_meas_file,
            "amplitudes": amplitudes,
            "missing_swps": missing_swps,
            "ton": ton,
            "toff": toff,
            "dt": dt
        }

# create BPE-compatible config dict, grouped by protocol
# then run BPE for each protocol type
for protocol_type in protocol_types:
    logging.info("Start extraction for protocol {}".format(protocol_type))
    cells_filtered = filter_measurements_by_protocol(measurement_dict, protocol_type)

    # create a new config dict that will become the input to BluePyEFe
    BPE_config = {
        'path': args.input_path,
        'features': config['features'],
        'format': config['format'],
        'comment': config['comment'],
        'options': config['options'],
        'cells': {}
    }

    for cell in cells_filtered:
        # these variables have the same value along the measurement protocol txts (for a given cell)
        amplitudes = []
        ton, toff, dt = None, None, None

        # these variables are meant to change depending on the measurement protocol txt content
        files = []
        exclude = []

        for measurement in measurement_dict[cell]:
            measurement_protocol = measurement_dict[cell][measurement]  # this is the content of the protocol.txt belonging to this specific cell and measurement

            # skip if not current protocol, will be processed later if not already
            if measurement_protocol['protocol_type'] != protocol_type:
                continue

            # these are pretty much read once and then get overwritten by the same value
            amplitudes = measurement_protocol['amplitudes']
            ton, toff, dt = measurement_protocol['ton'], measurement_protocol['toff'], measurement_protocol['dt']

            # these lists are expanded as we read out from the protocol.txts
            files.append(measurement_protocol['measurement_file'])
            missing_swps = []
            for missing_swp in measurement_protocol['missing_swps']:
                missing_swps.append(missing_swp)
            exclude.append(missing_swps)

        BPE_config['cells'][cell] = {
            'v_corr': config['protocol']['v_corr'],
            'ljp': config['protocol']['ljp'],
            'experiments': {
                'step': {
                    'location': config['protocol']['location'],
                    'files': files,
                    'dt': dt,
                    'amplitudes': amplitudes,
                    'hypamp': config['protocol']['hypamp'],
                    'ton': ton,
                    'toff': toff
                }
            },
            'exclude': exclude,
            'exclude_unit': [[config['options']['target_unit']] for exc in range(len(exclude))]
        }

        # add further missing keys
        BPE_config['options']['target'] = amplitudes

    # run feature extraction
    output_path_protocol = "{}/{}".format(args.output_path, protocol_type)
    extractor = bpefe.Extractor(output_path_protocol, BPE_config)
    extractor.create_dataset()
    extractor.create_metadataset()
    extractor.plt_traces()
    extractor.extract_features()
    try:
        extractor.collect_global_features()
    except AttributeError:
        logging.warning("This version of BluePyEfe does not support global feature collection. Skipping.")
    extractor.mean_features()
    extractor.plt_features()

    extractor.feature_config_cells()
    try:
        extractor.feature_config_meas()
    except AttributeError:
        logging.warning("This version of BluePyEfe does not support feature extraction separately for each measurement. Skipping.")
    extractor.feature_config_all()
