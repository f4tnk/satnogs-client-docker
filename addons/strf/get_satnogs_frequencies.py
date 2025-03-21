import requests

with open("frequencies.txt","w") as f:
    for x in requests.get("https://db.satnogs.org/api/transmitters/?alive=true&format=json").json():
        norad_id = x['norad_cat_id'] if x["norad_follow_id"] is None else x["norad_follow_id"]
        if x['downlink_low'] is not None:
            f.write(f"{norad_id} {x['downlink_low'] / 10e5:.3f}\n")
            
        if x['downlink_high'] is not None:
            f.write(f"{norad_id} {x['downlink_high'] / 10e5:.3f}\n")
