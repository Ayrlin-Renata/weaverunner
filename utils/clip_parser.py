import struct
import zlib
from PIL import Image
import io


def iter_csf_chunks(f):
    """
    A generator that iterates over the chunks in a CSFCHUNK file,
    yielding the chunk name, data, and absolute start offset.
    """
    file_header = f.read(24)
    
    if len(file_header) < 24 or not file_header.startswith(b'CSFCHUNK'):
        raise ValueError("Invalid .clip file header.")
    offset = 24
    
    while True:
        chunk_start_offset = offset
        chunk_header = f.read(16)
        
        if len(chunk_header) < 16: break
        magic, name, _, size = struct.unpack('>4s4s4sI', chunk_header)
        
        if magic != b'CHNK': break
        chunk_data = f.read(size)
        
        if len(chunk_data) < size: break
        yield name, bytes(chunk_data), chunk_start_offset
        offset += 16 + size


def get_external_chunk_data_by_id(clip_file_path, external_id_bytes):
    """
    Finds and returns the binary data for a specific external chunk by its ID
    and its absolute file offset.
    """
    print(f"  [Parser Log] Searching for external chunk with ID: {external_id_bytes.decode('ascii')}")
    with open(clip_file_path, 'rb') as f:
        for chunk_name, chunk_data, chunk_offset in iter_csf_chunks(f):
            if chunk_name == b'Exta':
                try:
                    if len(chunk_data) < 8:
                        print(f"  [Parser Log] 'Exta' chunk at offset {chunk_offset} is too small for name_length. Skipping.")
                        continue
                    name_length = int.from_bytes(chunk_data[:8], 'big')
                    
                    if len(chunk_data) < 8 + name_length + 8:
                        print(f"  [Parser Log] 'Exta' chunk at offset {chunk_offset} is too small for its name and size fields. Skipping.")
                        continue
                    chunk_id_bytes = chunk_data[8 : 8 + name_length]
                    try:
                        found_id_bytes = chunk_id_bytes.strip(b'\x00')
                        print(f"  [Parser Log] Found 'Exta' chunk with ID: {found_id_bytes.decode('ascii')} at offset {chunk_offset}")
                    except UnicodeDecodeError:
                        print(f"  [Parser Log] Found 'Exta' chunk with non-ascii ID at offset {chunk_offset}. Skipping.")
                        continue
                    
                    if found_id_bytes == external_id_bytes:
                        print(f"  [Parser Log] Match found! Extracting data.")
                        binary_data_offset = 8 + name_length + 8
                        data_blob_size = int.from_bytes(chunk_data[8 + name_length : binary_data_offset], 'big')
                        expected_total_size = binary_data_offset + data_blob_size
                        
                        if len(chunk_data) != expected_total_size:
                             print(f"  [Parser Log] Warning: Size mismatch in 'Exta' chunk. Data length is {len(chunk_data)}, but expected {expected_total_size} (header + blob). May have padding.")
                        
                        if len(chunk_data) < expected_total_size:
                            print(f"  [Parser Log] Error: 'Exta' chunk is smaller than expected. Data length {len(chunk_data)}, expected {expected_total_size}. Skipping.")
                            continue
                        blob_absolute_offset = chunk_offset + 16 + binary_data_offset
                        return chunk_data[binary_data_offset : binary_data_offset + data_blob_size], blob_absolute_offset
                except (IndexError, struct.error) as e:
                    print(f"  [Parser Log] Error parsing an 'Exta' chunk at offset {chunk_offset}: {e}")
                    continue
    print(f"  [Parser Log] Search complete. Chunk with ID {external_id_bytes.decode('ascii')} was not found.")
    return None, None


def parse_chunk_with_blocks(d):
    """
    Parses a BlockData blob which can contain multiple block types,
    to extract compressed data. Adapted from reference implementation.
    """
    BlockDataBeginChunk = 'BlockDataBeginChunk'.encode('UTF-16BE')
    BlockDataEndChunk = 'BlockDataEndChunk'.encode('UTF-16BE')
    BlockStatus = 'BlockStatus'.encode('UTF-16BE')
    BlockCheckSum = 'BlockCheckSum'.encode('UTF-16BE')
    bitmap_blocks = []
    ii = 0
    data_block_count = 0
    print("  [Parser Log] Starting sequential block parsing...")
    
    while ii < len(d):
        block_size = 0
        try:
            if ii + 4 + len(BlockStatus) <= len(d) and d[ii:ii+4+len(BlockStatus)] == b'\0\0\0\x0b' + BlockStatus:
                status_count = int.from_bytes(d[ii+26+4:ii+30+4], 'big')
                
                if data_block_count != status_count:
                    print(f"  [Parser Log] Warning: Mismatch in block count in BlockStatus, {data_block_count} != {status_count}")
                block_size = status_count * 4 + 12 + (len(BlockStatus)+4)
            elif ii + 4 + len(BlockCheckSum) <= len(d) and d[ii:ii+4+len(BlockCheckSum)] == b'\0\0\0\x0d' + BlockCheckSum:
                block_size = 4 + len(BlockCheckSum) + 12 + data_block_count * 4
            elif ii + 8 + len(BlockDataBeginChunk) <= len(d) and d[ii+8:ii+8+len(BlockDataBeginChunk)] == BlockDataBeginChunk:
                block_size = int.from_bytes(d[ii:ii+4], 'big')
                
                if ii + block_size > len(d):
                    print(f"  [Parser Log] BlockDataBeginChunk size {block_size} exceeds data length. Ending parse.")
                    break
                expected_end_marker = b'\0\0\0\x11' + BlockDataEndChunk
                read_end_marker_offset = ii + block_size - (4 + len(BlockDataEndChunk))
                
                if read_end_marker_offset < ii or d[read_end_marker_offset : read_end_marker_offset + len(expected_end_marker)] != expected_end_marker:
                    print(f"  [Parser Log] BlockDataBeginChunk at offset {ii} has invalid size or missing/mismatched end marker. Ending parse.")
                    break
                block_content = d[ii+8+len(BlockDataBeginChunk) : read_end_marker_offset]
                has_data = int.from_bytes(block_content[4*4:4*5], 'big')
                
                if has_data == 1:
                    subblock_data = block_content[7*4:]
                    bitmap_blocks.append(subblock_data)
                else:
                    bitmap_blocks.append(None)
                data_block_count += 1
            else:
                print(f"  [Parser Log] Unrecognized block structure at offset {ii}. Data: {d[ii:ii+50]!r}. Ending parse.")
                break
            
            if block_size <= 0:
                print(f"  [Parser Log] Invalid or zero block size ({block_size}) calculated at offset {ii}. Ending parse.")
                break
            ii += block_size
        except (IndexError, struct.error) as e:
            print(f"  [Parser Log] Error or end of data while parsing block at offset {ii}: {e}. Ending parse.")
            break
    print(f"  [Parser Log] Finished parsing. Found {len(bitmap_blocks)} data block(s) sequentially.")
    return bitmap_blocks


def _read_int_be(b_io):
    """
    Reads a 4-byte big-endian integer from a BytesIO stream.
    """
    return int.from_bytes(b_io.read(4), 'big')


def _read_str_utf16_be(b_io):
    """
    Reads a length-prefixed UTF-16 BE string from a BytesIO stream.
    """
    str_size = _read_int_be(b_io)
    string_data = b_io.read(2 * str_size)
    return string_data.decode('UTF-16-BE')


def reconstruct_layer_from_tiles(canvas_image, compressed_blocks, attribute_blob):
    """
    Reconstructs a layer by parsing the Attribute blob and decompressing,
    re-ordering channels, and pasting individual tiles onto the canvas.
    """
    try:
        b_io = io.BytesIO(attribute_blob)
        _read_int_be(b_io)
        _read_int_be(b_io)
        _read_int_be(b_io)
        _read_int_be(b_io)
        param_str = _read_str_utf16_be(b_io)
        
        if param_str != "Parameter":
             raise ValueError(f"Expected 'Parameter' string, but found '{param_str}'")
        bitmap_width = _read_int_be(b_io)
        bitmap_height = _read_int_be(b_io)
        block_grid_width = _read_int_be(b_io)
        block_grid_height = _read_int_be(b_io)
        pixel_packing_params = [_read_int_be(b_io) for _ in range(16)]
        _read_str_utf16_be(b_io)
        print(f"Found tile map: {block_grid_width} x {block_grid_height} grid.")
        print(f"Layer bitmap dimensions: {bitmap_width} x {bitmap_height}")
        
        if block_grid_width * block_grid_height != len(compressed_blocks):
             print(f"Warning: Tile map grid size ({block_grid_width*block_grid_height}) does not match number of data blocks found ({len(compressed_blocks)}).")
        TILE_DIM = 256
        k = TILE_DIM * TILE_DIM
        packing_type = (pixel_packing_params[1], pixel_packing_params[2])
        
        if packing_type != (1, 4):
            raise NotImplementedError(f"Unsupported pixel packing type: {packing_type}. Only RGBA (1, 4) is supported.")
        
        for i in range(block_grid_height):
            for j in range(block_grid_width):
                block_index = i * block_grid_width + j
                
                if block_index >= len(compressed_blocks): continue
                block = compressed_blocks[block_index]
                
                if not block: continue
                try:
                    pixel_data_bytes = zlib.decompress(block)
                except zlib.error:
                    continue
                
                if len(pixel_data_bytes) != 5 * k: continue
                pixel_data = memoryview(pixel_data_bytes)
                block_img_alpha = Image.frombuffer("L", (TILE_DIM, TILE_DIM), pixel_data[0:k], 'raw', "L", 0, 1)
                block_img_bgrx = Image.frombuffer("RGBA", (TILE_DIM, TILE_DIM), pixel_data[k:5*k], 'raw', "RGBA", 0, 1)
                b, g, r, _ = block_img_bgrx.split()
                block_result_img = Image.merge("RGBA", (r, g, b, block_img_alpha))
                paste_x = j * TILE_DIM
                paste_y = i * TILE_DIM
                
                if paste_x < bitmap_width and paste_y < bitmap_height:
                    crop_width = min(TILE_DIM, bitmap_width - paste_x)
                    crop_height = min(TILE_DIM, bitmap_height - paste_y)
                    
                    if crop_width < TILE_DIM or crop_height < TILE_DIM:
                        block_result_img = block_result_img.crop((0, 0, crop_width, crop_height))
                    background_tile = canvas_image.crop((paste_x, paste_y, paste_x + crop_width, paste_y + crop_height))
                    composited_tile = Image.alpha_composite(background_tile, block_result_img)
                    canvas_image.paste(composited_tile, (paste_x, paste_y))
    except (struct.error, ValueError, IndexError, NotImplementedError) as e:
        print(f"Error parsing attribute blob or reconstructing tiles: {e}")
