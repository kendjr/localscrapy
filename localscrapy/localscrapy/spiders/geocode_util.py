import geocoder

def get_geocode(address):
    if not address:
        return None
    try:
        g = geocoder.osm(address)
        if g.ok:
            return {
                'lat': g.lat,
                'lng': g.lng
            }
    except:
        pass
    return None 