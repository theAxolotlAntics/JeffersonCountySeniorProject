from MapModule import create_map

address = "549 Route 28, Brookville, PA 15825-7100"
out = create_map(address, ID="549_Route_28")
print("Map saved to:", out)