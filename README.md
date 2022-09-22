## Automated feature extraction using BluePyEfe

This script scans through an input directory (organized in a certain way), find cells and their respective measurements, group cells by protocol and run a BPE feature extraction for all cells belonging to the same protocol. 

To run this script the following components are required:
 - **input directory** contianing data organized in a particular structure
 - **protocol.txt** files for each measurement
 - **config.json**
 - **output directory**: BPE output will be saved here

### Input data - directory structure
Inside the input directory following structure is assumed by the script: each cell has a subdirectory under the input directory. Each cell directory has one or more measurement subdirectories. Each measurement subdirectory has measurement files and a protocol.txt that provides the protocol for a given measurement as well as other information. Summary:

    input_dir
	    cell1_dir
		    meas1_dir
			    - meas1_ch1_file
			    - meas1_ch2_file
			    - protocol.txt
		    meas2_dir
		    ...
	    cell2_dir
	    ...
	   
### Protocol files
These protocol.txt files either have 5 or 6 rows containing the following information in each row:

 - **protocol name**: unique identifier of protocol; used for grouping
 - **channel**: which file contains the voltage data; this string is searched for in the measurement filenames)
 - **sampling rate** (Hz)
 - **parameter list**: a 3-tuple containing (ton, toff, duration) - needed for BPE
 - **amplitudes list**: list of current injection amplitudes (pA)
 - **missing sweeps list**: list of indices of amplitudes for which the measurements are deemed to be unused for some reason

### Config JSON
The script requires a config.json that contains further (protocol-unspecific) configuration parameters that are required to run BluePyEfe (e.g.: list of features to be extracted).

### How to run the script
The script takes three parameters:

    -cp / --config-path: Path to configuration JSON
    -ip / --input-path: Root path for input directory containing raw electrophysiological data
    -op / --output-path: Directory where BPE feature extraction results should be saved

   Example run:
   

    python extract.py -cp ./config_example.json -ip ./input_directory_example -op ./output_directory

To run the script you need to have BluePyEfe installed. If you want to collect global features (e.g.: rheobase current and all features grouped by rheobase current, fI-curve slopes, etc.) please install the following, modified version of BPE: https://github.com/blazma/BluePyEfe





