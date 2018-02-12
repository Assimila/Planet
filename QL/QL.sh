#!/bin/bash

# Create a quicklook (QL) in 4,3,2 (RGB) band combination
# for every PlanetScope image in the current directory and
# an animated GIF with all the individual QLs

for image in *.tif
do
    DoY=`echo $image | cut -d_ -f3-4`

    # Scale images from original TOA refl to 0-255 values
    # stretch values are totally empirical...
    gdal_translate -b 2 -of GTiff -ot Byte -scale 3000 11000 0 255 $image $image.b2.tif
    gdal_translate -b 3 -of GTiff -ot Byte -scale 2000 10000 0 255 $image $image.b3.tif
    gdal_translate -b 4 -of GTiff -ot Byte -scale 2000 7000 0 255 $image $image.b4.tif

    # Create a PNG from the individual scaled bands in a 4,2,3 order
    # 4 - NIR
    # 2 - Green
    # 3 - Blue

    convert $image.b4.tif $image.b2.tif $image.b3.tif -font AvantGarde-Book -gravity Northeast -pointsize 40 -fill white -draw 'text 10,18 " '$DoY'' -channel RGB -combine $image.423.RGB.png

    rm $image.b2.tif $image.b3.tif $image.b4.tif

done

image="PSOrthoTile.gif"
convert -loop 0 -delay 100 *423.RGB.png $image
