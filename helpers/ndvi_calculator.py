# coding=utf-8
"""
Purpose
    The ndvi_calculator script:
        - Calculate NDVI and save output to new directory (../ndvi/)

      Compulsory steps before running the script:
      1 - Must first run downloadPlanet_subset.py and store in ../images/
          directory

"""

import glob
import os
import numpy as np
from osgeo import gdal

def ndvi_equation(red, nir):

    np.seterr(divide='ignore', invalid='ignore')
    ndvi = (nir - red)/(nir + red)

    return ndvi

def ndvi_calculator(file_location="../images/*.tif"):

    """
    Function to calculate NDVI.

    :param file_location:  Location of the Planet .tif files.

    :return: N/A

    """

    filelist = glob.glob(file_location)
    print str(len(filelist)) + " files found.\n"

    # Set up counter for tracking purposes
    c=0

    for f in filelist:

        ds = gdal.Open(f)

        red = np.array(ds.GetRasterBand(3).ReadAsArray(), dtype=float)
        nir = np.array(ds.GetRasterBand(4).ReadAsArray(), dtype=float)

        ndvi = ndvi_equation(red, nir)

        [cols, rows] = ndvi.shape
        arr_min = ndvi.min()
        arr_max = ndvi.max()
        arr_out = np.where((ndvi == np.nan), -999, ndvi)

        split = f.split("/")

        outfilename = "../ndvi/" + split[1][0:-7] + "_ndvi.tif"

        driver = gdal.GetDriverByName("GTiff")
        outdata = driver.Create(outfilename, rows, cols, 1, gdal.GDT_Float32)

        outdata.SetGeoTransform(ds.GetGeoTransform())  # sets same geotransform as input
        outdata.SetProjection(ds.GetProjection())  # sets same projection as input
        outdata.GetRasterBand(1).WriteArray(arr_out)
        outdata.GetRasterBand(1).SetNoDataValue(-999)  # if you want these values transparent

        outdata.FlushCache()  # saves to disk!!
        outdata = None
        band = None
        ds = None


# Run the method!
ndvi_calculator()