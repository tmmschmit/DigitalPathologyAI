# DigitalPathologyAI

## Installation
First commit of the code for the UCL-led collaboration on Digital Pathology
In this code, we use conda and pytorch to uniformize effort.
To set up your Python environment:
- Install `conda` or `miniconda` for your operating system.

For Linux:
- Create a Conda environment from the `environment.yml` file in the repository root, and activate it:
```shell script
conda env create --file environment.yml
conda activate DigitalPathologyAI
```
For Windows:
- Create a Conda environment from the `environment_win.yml` file in the repository root, and activate it:
```shell script
conda env create --file environment_win.yml
conda activate DigitalPathologyAI
```

To then set up your file as a module, please use
```shell script
conda-develop /path/to/DigitalPathologyAI/
```

## Preprocessing
The first step to run the different code is to run the TileDataset.sh shell file, and to point it at your directory containing your datafiles
```shell script
source TileDataset.sh SlideDirectory/
```

This will, in order, do:

1. create a folder (Preprocessing) containing mask, patches, wsi, and stitches 
   1. A folder containing, for each slide, jpg showing the mask separation between tiles and background (mask)
   2. A folder containing, for each slide, h5 files containgCoords of each tile of interest within each slide (patches)
   3. A folder containing, for each slide, jpg showing a stitches of individual tiles at low resolution (stitches)
   4. A folder containing all of the wsi slides (moved there to minimize space usage) (wsi)
2. Apply a NN to extract the coords of the patches that are within the tumour and update the patches csv file
	 
The data processing workflow is displayed below, where the tumorous parts in the whole slides images are used as region of interest for developing multiple applications including tumour subtype classification, mitosis detection and unsupervised culstering.  	 
![image](https://user-images.githubusercontent.com/44832648/137453431-ebe11082-40f9-4b23-937e-41a78a5949e1.png)

## Code Division