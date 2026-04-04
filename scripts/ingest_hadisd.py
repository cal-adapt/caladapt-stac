# Okay, now make a ingest script for the HadISD dataset. 

# This one is here: https://cadcat.s3.amazonaws.com/index.html#hadisd/

# The files are organized by station, with one file per station. each file is a zarr. 

# name: hadisd-station-zarrs

# description: Cloud-optimized version of Met Office Hadley Center's global sub-daily dataset based on the ISD dataset from NOAA's NCEI. (lmk if you think of a way to shorten this)

# The filename is as follows: HadISD_{station_id}.zarr
# The station_id comes from the hadisd_stations.csv which is at this path:HADISD_STATION_COORDS_URL 
# It is the column "station id" with a space not an underscore. 

# also add the geometries! They are the same as the climate profiles geometries. 

# for the producer, it is Met Office Hadley Centre and the host and processor is cal-adapt. just hard code that. the link to the met office is here: https://www.metoffice.gov.uk/hadobs/hadisd/

# let me know if theres any other info you need from me. 