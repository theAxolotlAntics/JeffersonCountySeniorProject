from MapModule import create_map

address = "549 Route 28, Brookville, PA 15825-7100"
out = create_map(address, ID="549_Route_28", force_refresh=True) #the force_refresh makes it regenerate the map, otherwise it will use the cached version if it exists
print("Map saved to:", out)