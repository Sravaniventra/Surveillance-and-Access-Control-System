
CCTV Indoor Person Detection - v4 2023-05-20 12:34pm
==============================

This dataset was exported via roboflow.com on September 16, 2026 at 2:22 PM GMT

Roboflow is an end-to-end computer vision platform that helps you
* collaborate with your team on computer vision projects
* collect & organize images
* understand and search unstructured image data
* annotate, and create datasets
* export, train, and deploy computer vision models
* use active learning to improve your dataset over time

For state of the art Computer Vision training notebooks you can use with this dataset,
visit https://github.com/roboflow/notebooks

To find over 100k other datasets and pre-trained models, visit https://universe.roboflow.com

The dataset includes 1350 images.
Persons are annotated in YOLOv8 Oriented Object Detection format.

The following pre-processing was applied to each image:

The following augmentation was applied to create 3 versions of each source image:
* 50% probability of horizontal flip
* Random rotation of between -15 and +15 degrees
* Random shear of between -15° to +15° horizontally and -15° to +15° vertically
* Random brigthness adjustment of between -25 and +25 percent
* Random exposure adjustment of between -15 and +15 percent
* Salt and pepper noise was applied to 1 percent of pixels

The following transformations were applied to the bounding boxes of each image:
* Random rotation of between -10 and +10 degrees
* Random shear of between -5° to +5° horizontally and -5° to +5° vertically
* Random brigthness adjustment of between -10 and +10 percent


