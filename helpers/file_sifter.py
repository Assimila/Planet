# coding=utf-8
"""
Purpose
  The file_sifter script:
    - The Planet API does not allow you to specify "Area Coverage" so this is
      a manual step to remove slither images.

    - To open each image and assess the number of noData pixels and delete
      those below a user-specified threshold.

      Compulsory steps before running the script:
      1 - Must first run downloadPlanet_subset.py and store in images/
          directory

"""

import glob
import os
import numpy as np
from osgeo import gdal

def file_sifter(file_location="../images/*.tif", data_threshold=30):

    """
    Function to 'sift' through the data and remove those which do not
    cover the AOI by at least the percentage specified.

    :param file_location:  Location of the Planet .tif files
    :param data_threshold: Percentage of present data required
                           for the file to be kept. i.e. data_threshold=30
                           means that there must be at least 30% of data
                           values in the entire image.

    :return: N/A

    """

    filelist = glob.glob(file_location)
    print str(len(filelist)) + " files found.\n"

    # Set up counter for tracking purposes
    c=0

    for f in filelist:

        data = gdal.Open(f)
        array = np.array(data.GetRasterBand(1).ReadAsArray())

        # Get the total number of pixels in the array
        x, y = np.shape(array)
        total = float(x*y)

        # Get the total number of 'data' pixels (non NoData pixels)
        non_z = float(np.count_nonzero(array))

        # Calculate the AOI coverage
        aoi_coverage = float(non_z / total * 100.)

        array = None
        del data

        # If coverage is less than the data_threshold
        # move to another folder
        if aoi_coverage < data_threshold:

            split = f.split("/")
            newfilename = split[0] + "/sift/" + split[1]

            print f + ": does not meet AOI coverage, moving...",

            # Move the file to the sift bin
            os.rename(f, newfilename)

            print " done.  " + str(c)

        # Else, move on
        else:

            print "AOI coverage met for: " + f + "  " + str(c)

        c+=1


# Run the method!
file_sifter()
