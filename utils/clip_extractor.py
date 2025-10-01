import sqlite3
import argparse
from PIL import Image
import tempfile
import os
import shutil
from . import clip_parser


def find_and_extract_db(clip_file_path):
    """
    Parses a 'CSFCHUNK' format file to find the SQLite database.
    """
    print("Parsing CSFCHUNK file to find database...")
    try:
        with open(clip_file_path, 'rb') as f:
            for chunk_name, chunk_data, _ in clip_parser.iter_csf_chunks(f):
                if chunk_name == b'SQLi':
                    print("Found database chunk.")
                    db_data = chunk_data
                    
                    if not db_data.startswith(b'SQLite format 3\x00'):
                        db_data = bytes(b ^ 0x42 for b in db_data)
                        
                        if not db_data.startswith(b'SQLite format 3\x00'):
                            print("Error: De-obfuscation failed.")
                            return None, None
                    temp_dir = tempfile.mkdtemp()
                    db_path = os.path.join(temp_dir, 'database.sqlite')
                    with open(db_path, 'wb') as db_file:
                        db_file.write(db_data)
                    return db_path, temp_dir
        print("\nError: Could not find 'SQLi' chunk in the file.")
        return None, None
    except Exception as e:
        print(f"An error occurred while parsing CSFCHUNK file: {e}")
        return None, None


def extract_layer(db_path, clip_file_path, layer_name, output_png_path, export_db_path=None):
    """
    Connects to the DB, gathers all data following the reference script's logic,
    and reconstructs the final layer image.
    """
    print(f"Processing database file: {db_path}")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.text_factory = bytes
        cursor = conn.cursor()
        print(f"Searching for layer: '{layer_name}'...")
        cursor.execute("SELECT _PW_ID, MainId, LayerName, LayerRenderMipmap FROM Layer")
        all_layers = cursor.fetchall()
        target_layer_row = None
        
        for row in all_layers:
            try:
                if row['LayerName'].decode('utf-8').strip('\x00') == layer_name:
                    target_layer_row = row
                    break
            except (UnicodeDecodeError, AttributeError):
                pass
        
        if not target_layer_row:
            raise ValueError(f"Layer '{layer_name}' not found.")
        layer_main_id = target_layer_row['MainId']
        print(f"Found layer '{layer_name}' with MainId: {layer_main_id}")
        print("\nFinding the tile map...")
        cursor.execute("SELECT BaseMipmapInfo FROM Mipmap WHERE MainId = ?", (target_layer_row['LayerRenderMipmap'],))
        mipmap_row = cursor.fetchone()
        
        if not mipmap_row: raise ValueError("Could not find Mipmap entry for layer.")
        cursor.execute("SELECT Offscreen FROM MipmapInfo WHERE MainId = ?", (mipmap_row['BaseMipmapInfo'],))
        mipmap_info_row = cursor.fetchone()
        
        if not mipmap_info_row: raise ValueError("Could not find MipmapInfo entry for layer.")
        offscreen_id = mipmap_info_row['Offscreen']
        cursor.execute("SELECT Attribute, BlockData FROM Offscreen WHERE MainId = ?", (offscreen_id,))
        offscreen_row = cursor.fetchone()
        
        if not offscreen_row: raise ValueError("Could not find the specific Offscreen entry for the layer.")
        attribute_blob = offscreen_row['Attribute']
        block_data_ref = offscreen_row['BlockData']
        print("Successfully retrieved the tile map (Attribute blob).")
        all_compressed_blocks = []
        
        if block_data_ref and block_data_ref.startswith(b'extrnlid'):
            ext_id_bytes = block_data_ref.strip(b'\x00')
            print(f"\nFound pixel data chunk reference: {ext_id_bytes.decode('ascii')}")
            print(f"--- Processing external chunk {ext_id_bytes.decode('ascii')} ---")
            raw_blockdata, blob_offset = clip_parser.get_external_chunk_data_by_id(clip_file_path, ext_id_bytes)
            
            if raw_blockdata:
                print(f"  [Extractor Log] Analyzing data blob for this chunk, which starts at file offset: {blob_offset} (0x{blob_offset:X})")
                compressed_blocks = clip_parser.parse_chunk_with_blocks(raw_blockdata)
                
                if compressed_blocks:
                    all_compressed_blocks = compressed_blocks
                    print(f"  Found {len([b for b in all_compressed_blocks if b])} compressed data block(s).")
                else:
                    print("  Warning: No compressed data blocks were found in this chunk.")
            else:
                print(f"  Warning: Could not retrieve data for chunk {ext_id_bytes.decode('ascii')}.")
        else:
            print("\nLayer does not appear to have an external pixel data chunk.")
        
        if not all_compressed_blocks:
            print("\nWarning: Layer appears to be empty (no compressed data blocks found).")
        print(f"\nTotal compressed data blocks found: {len([b for b in all_compressed_blocks if b])}")
        print(f"Total blocks (including empty): {len(all_compressed_blocks)}")
        
        if not output_png_path:
             print("No output path specified. Skipping final image reconstruction.")
             return
        print("Reconstructing final image from tiles...")
        cursor.execute("SELECT CanvasWidth, CanvasHeight FROM Canvas LIMIT 1")
        canvas_dims = cursor.fetchone()
        canvas_width, canvas_height = int(canvas_dims['CanvasWidth']), int(canvas_dims['CanvasHeight'])
        final_image = Image.new("RGBA", (canvas_width, canvas_height), (0,0,0,0))
        clip_parser.reconstruct_layer_from_tiles(final_image, all_compressed_blocks, attribute_blob)
        final_image.save(output_png_path, "PNG")
        print(f"\nSuccessfully saved layer '{layer_name}' to: {output_png_path}")
    except (sqlite3.Error, ValueError) as e:
        print(f"An error occurred: {e}")
    finally:
        if conn: conn.close()


def main():
    """
    Main function to handle command-line arguments and dispatch tasks.
    """
    parser = argparse.ArgumentParser(description="Extract a raster layer from a Clip Studio Paint (.clip) file.")
    parser.add_argument("clip_file", help="Path to the input .clip file.")
    parser.add_argument("--layer-name", required=True, help="The name of the layer to process.")
    parser.add_argument("--output-png", required=True, help="Path for the final output .png file.")
    parser.add_argument("--export-db", help="Path to save the extracted SQLite database.")
    args = parser.parse_args()
    print(f"Opening .clip file: {args.clip_file}")
    temp_dir = None
    try:
        db_path, temp_dir = find_and_extract_db(args.clip_file)
        
        if not db_path: return
        
        if args.export_db:
            print(f"Exporting database to: {args.export_db}")
            shutil.copyfile(db_path, args.export_db)
            print("Database exported successfully.")
        extract_layer(db_path, args.clip_file, args.layer_name, args.output_png)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("Cleaned up temporary files.")

if __name__ == "__main__":
    main()
