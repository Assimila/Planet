# coding=utf-8
"""
Purpose
  The downloadPlanet script:
    - Download free Planet data using their API for the area of
      interest (aoi) specified as a bounding box in Lat/Lon in
      GeoJSON format -- see aoi variable --
      The script only gets the PlanetScope OrthoTiles (PSOrthoTile)
      and the RapidEye OrthoTiles (REOrthoTile) but different Planet
      ItemTypes could be donwloaded:
      https://www.planet.com/docs/reference/data-api/items-assets/#item-type

      Compulsory steps before running the script:      
      1 - It is neccesary first to create an account. Set the user login 
          details in YOUR_EMAIL and YOUR_PASSWD strings within the script
      2 - Get the API key at planet.com/account/
          Store the key as en environmental variable, e.g. in .bashrc
          export PL_API_KEY=a3a64774d30c4749826b6be445489d3b # (not a real key)
      3 - Install the Planet API, see:
          https://github.com/planetlabs/planet-client-python

    - To run the script and get data (2 images):
      python downloadPlanet.py

      To download more than 2 images, modify the NumberOfImages variable 

"""

__author__ = "Gerardo López Saldaña"
__version__ = "0.2 (20.10.2017)"
__email__ = "gerardo.lopezsaldana@assimila.eu"

import os
import requests

from planet import api
from planet.api import filters
from sys import stdout

# GeoJSON AOI
aoi = {
  "type": "Polygon",
  "coordinates": [
    [
      [-122.54, 37.81],
      [-122.38, 37.84],
      [-122.35, 37.71],
      [-122.53, 37.70],
      [-122.54, 37.81]
    ]
  ]
}

# Get API key
api_key = api.ClientV1().login( 'YOUR_EMAIL', 'YOUR_PASSWD' )

# Create client
client = api.ClientV1( api_key = api_key['api_key'] )

# Build a query using the AOI and a cloud_cover filter
# that get images with lower than 10% cloud cover
# and acquired before Nov 1st, 2017
query = filters.and_filter(
    filters.geom_filter(aoi),
    filters.range_filter( 'cloud_cover', lt = 0.1 ),
    filters.date_range( 'acquired', lte = '2017-11-01T00:00:00.000Z' )
)

# Build a request for only PlanetScope imagery
request = filters.build_search_request(
    query, item_types = [ 'PSOrthoTile', 'REOrthoTile' ]
)

# Get results
result = client.quick_search(request)

# Setup auth
session = requests.Session()
session.auth = ( api_key['api_key'], '')

# Set asset type to download
asset_type = 'analytic'

stdout.write('item_id,item_type,cloud_cover,date\n')

# items_iter returns a limited iterator of all results,
# behind the scenes, the client is paging responses from the API
NumberOfImages = 2
for item in result.items_iter( limit = NumberOfImages ):
    props = item['properties']
    item_id = item['id']
    item_type = item['properties']['item_type']

    stdout.write('{0},{item_type},{cloud_cover},' \
                 '{acquired}\n'.format(item['id'], **props))

    # Request an item
    item_to_download = \
        session.get(
        ("https://api.planet.com/data/v1/item-types/" +
        "{}/items/{}/assets/").format(item_type, item_id))

    # Extract the activation url from the item for the desired asset
    item_activation_url = item_to_download.json()[
                          asset_type]["_links"]["activate"]

    # Request activation
    response = session.post( item_activation_url )

    # HTTP 204: Success, No Content to show
    if response.status_code <> 204:
        print response.status_code

    # Get location of the asset
    asset_location_url = item_to_download.json()[asset_type]['location']

    # Get the data
    request = session.get( asset_location_url, stream = True )
    fname = os.path.join( '/tmp', request.headers['content-disposition'] )
    print 'Saving %s' % ( fname )
    with open( fname, 'wb') as fd:
        for chunk in request.iter_content( chunk_size=128 ):
            fd.write(chunk)

