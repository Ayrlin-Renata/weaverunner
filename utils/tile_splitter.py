from PIL import Image
import os
import sys


def run_split(input_path, output_dir=None):
    """
    Splits a single large image into 512x512 tiles.
    
    Args:
        input_path (str): The full path to the source image.
        output_dir (str, optional): The directory to save the tiles in. 
                                    Defaults to the same directory as the input file.
    """
    try:
        if not output_dir:
            output_dir = os.path.dirname(input_path)
        image = Image.open(input_path).convert("RGBA")
        width, height = image.size
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        os.makedirs(output_dir, exist_ok=True)
        tile_size = 512
        tiles_x = (width + tile_size - 1) // tile_size
        tiles_y = (height + tile_size - 1) // tile_size
        print(f"Splitting '{base_name}' into {tiles_x * tiles_y} tiles...")
        
        for y in range(tiles_y):
            for x in range(tiles_x):
                tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                left = x * tile_size
                upper = y * tile_size
                right = min(left + tile_size, width)
                lower = min(upper + tile_size, height)
                
                if left < width and upper < height:
                    region = image.crop((left, upper, right, lower))
                    tile.paste(region, (0, 0))
                tile_filename = f"{base_name}_{x}_{y}.png"
                tile.save(os.path.join(output_dir, tile_filename))
        print(f"Tile splitting complete for '{base_name}'.")
        return True
    except Exception as e:
        print(f"ERROR during tile splitting: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tile_splitter.py <input_image.png>")
        sys.exit(1)
    run_split(sys.argv[1])
