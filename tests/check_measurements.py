import argparse
import glob
import json


parser = argparse.ArgumentParser(description='This test script checks for each measurement if feature extraction failed')
parser.add_argument('-m', type=str, required=True, help='txt file containing list of measurements separated by newline')
parser.add_argument('-o', type=str, required=True, help='extraction output folder (Unix style path, e.g: ../output)')
args = parser.parse_args()

measurements_text_path = args.m
extraction_output_path = args.o

results = {}
with open(measurements_text_path, "r") as measurement_text_file:
    measurements_lines = measurement_text_file.readlines()

    for measurements_line in measurements_lines:
        measurement = measurements_line.split()[0]
        cell = measurement[:-2]

        # check if measurement folder exists
        measurement_folder_path = "{}/**/{}/{}".format(extraction_output_path, cell, measurement)
        meas_ok = bool(glob.glob(measurement_folder_path, recursive=True))

        # check if measurement features exist in measurement file
        feat_ok = False
        if meas_ok:
            features_file_path = "{}/**/features.json".format(measurement_folder_path)
            features_file_glob = glob.glob(features_file_path, recursive=True)
            if features_file_glob:
                with open(features_file_glob[0], "r") as features_file:
                    features_json = json.load(features_file)
                    if features_json:
                        feat_ok = True

        results[measurement] = (meas_ok, feat_ok)

with open("check_measurements.txt", "w") as check_meas:
    for measurement, (meas_ok, feat_ok) in results.items():
        meas_text = "OK,\t" if meas_ok else "NOT OK,"
        feat_text = "OK" if feat_ok else "NOT OK"
        check_meas.writelines([measurement, "\tfolder: {}\t\tfeatures: {}\n".format(meas_text, feat_text)])
