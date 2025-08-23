import os
import re
import gc
import sys
import time
import json
import argparse
from tqdm import tqdm
from multiprocessing import set_start_method, Process, Value, Lock, Event
from typing import List, Tuple, Optional
from collections import defaultdict, Counter
from copy import deepcopy
import inspect

import numpy as np
import torch
import requests
import filetype
from filelock import FileLock
import pypdfium2
from PIL import Image, ImageDraw, ImageFont

from pynvml import *
import psutil
import threading

# Fixed imports for Surya
try:
    from surya.detection import DetectionPredictor
    from surya.layout import LayoutPredictor
    from surya.recognition import RecognitionPredictor
    from surya.table_rec import TableRecPredictor
    from surya.foundation import FoundationPredictor
    from surya.common.surya.schema import TaskNames
except ImportError as e:
    print(f"Error importing Surya modules: {e}")
    print("Please ensure surya-ocr is installed: pip install surya-ocr")
    sys.exit(1)

IMAGE_DPI = 96  # Used for detection, layout, reading order
IMAGE_DPI_HIGHRES = 192  # Used for OCR, table rec
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")
RECOGNITION_RENDER_FONTS = os.path.join(FONT_DIR, "GoNotoCurrent-Regular.ttf")
RECOGNITION_FONT_DL_BASE = "https://github.com/satbyy/go-noto-universal/releases/download/v7.0"

worker_gpu = None
det_predictor = None
layout_predictor = None
rec_predictor = None
table_rec_predictor = None
foundation_predictor = None

resource_stats = {
    "cpu_sum": 0.0, "cpu_count": 0,
    "ram_sum": 0.0, "ram_count": 0,
    "gpu_util_sum": 0.0, "gpu_util_count": 0,
    "gpu_mem_sum": 0.0, "gpu_mem_count": 0
}

def start_resource_monitoring(gpu_ids, log_interval=1.0):
    process = psutil.Process(os.getpid())
    nvmlInit()

    def monitor():
        while True:
            try:
                cpu_percent = process.cpu_percent(interval=None)
                mem_info = process.memory_info().rss / 1024**2  # MB

                gpu_util_vals = []
                gpu_mem_vals = []

                for gpu_id in gpu_ids:
                    handle = nvmlDeviceGetHandleByIndex(gpu_id)
                    util = nvmlDeviceGetUtilizationRates(handle).gpu
                    mem = nvmlDeviceGetMemoryInfo(handle).used / 1024**2  # MB
                    gpu_util_vals.append(util)
                    gpu_mem_vals.append(mem)

                avg_gpu_util = sum(gpu_util_vals) / len(gpu_util_vals)
                avg_gpu_mem = sum(gpu_mem_vals) / len(gpu_mem_vals)

                resource_stats["cpu_sum"] += cpu_percent
                resource_stats["cpu_count"] += 1
                resource_stats["ram_sum"] += mem_info
                resource_stats["ram_count"] += 1
                resource_stats["gpu_util_sum"] += avg_gpu_util
                resource_stats["gpu_util_count"] += 1
                resource_stats["gpu_mem_sum"] += avg_gpu_mem
                resource_stats["gpu_mem_count"] += 1

                time.sleep(log_interval)
            except Exception as e:
                break

    import threading
    t = threading.Thread(target=monitor, daemon=True)
    t.start()

def get_text_size(text, font):
    im = Image.new(mode="P", size=(0, 0))
    draw = ImageDraw.Draw(im)
    _, _, width, height = draw.textbbox((0, 0), text=text, font=font)
    return width, height

def render_text(draw, text, s_bbox, bbox_width, bbox_height, font_path, box_font_size):
    font = ImageFont.truetype(font_path, box_font_size)
    text_width, text_height = get_text_size(text, font)
    while (text_width > bbox_width or text_height > bbox_height) and box_font_size > 6:
        box_font_size = box_font_size - 1
        font = ImageFont.truetype(font_path, box_font_size)
        text_width, text_height = get_text_size(text, font)

    # Calculate text position (centered in bbox)
    text_width, text_height = get_text_size(text, font)
    x = s_bbox[0]
    y = s_bbox[1] + (bbox_height - text_height) / 2

    draw.text((x, y), text, fill="black", font=font)

def get_font_path():
    font_path = RECOGNITION_RENDER_FONTS

    if not os.path.exists(font_path):
        os.makedirs(os.path.dirname(font_path), exist_ok=True)
        font_dl_path = f"{RECOGNITION_FONT_DL_BASE}/{os.path.basename(font_path)}"
        with requests.get(font_dl_path, stream=True) as r, open(font_path, 'wb') as f:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return font_path

def draw_text_on_image(bboxes, texts, image_size, font_path=None, max_font_size=60, res_upscale=2):
    if font_path is None:
        font_path = get_font_path()
    new_image_size = (image_size[0] * res_upscale, image_size[1] * res_upscale)
    image = Image.new("RGB", new_image_size, color="white")
    draw = ImageDraw.Draw(image)

    for bbox, text in zip(bboxes, texts):
        s_bbox = [int(coord * res_upscale) for coord in bbox]
        bbox_width = s_bbox[2] - s_bbox[0]
        bbox_height = s_bbox[3] - s_bbox[1]

        # Shrink the text to fit in the bbox if needed
        box_font_size = max(6, min(int(0.75 * bbox_height), max_font_size))
        render_text(draw, text, s_bbox, bbox_width, bbox_height, font_path, box_font_size)

    return image

def draw_bboxes_on_image(bboxes, image, labels=None, label_font_size=10, color: str | list = 'red'):
    polys = []
    for bb in bboxes:
        # Clockwise polygon
        poly = [
            [bb[0], bb[1]],
            [bb[2], bb[1]],
            [bb[2], bb[3]],
            [bb[0], bb[3]]
        ]
        polys.append(poly)

    return draw_polys_on_image(polys, image, labels, label_font_size=label_font_size, color=color)

def draw_polys_on_image(corners, image, labels=None, box_padding=-1, label_offset=1, label_font_size=10, color: str | list = 'red'):
    draw = ImageDraw.Draw(image)
    font_path = get_font_path()
    label_font = ImageFont.truetype(font_path, label_font_size)

    for i in range(len(corners)):
        poly = corners[i]
        poly = [(int(p[0]), int(p[1])) for p in poly]
        draw.polygon(poly, outline=color[i] if isinstance(color, list) else color, width=1)

        if labels is not None:
            label = labels[i]
            text_position = (
                min([p[0] for p in poly]) + label_offset,
                min([p[1] for p in poly]) + label_offset
            )
            text_size = get_text_size(label, label_font)
            box_position = (
                text_position[0] - box_padding + label_offset,
                text_position[1] - box_padding + label_offset,
                text_position[0] + text_size[0] + box_padding + label_offset,
                text_position[1] + text_size[1] + box_padding + label_offset
            )
            draw.rectangle(box_position, fill="white")
            draw.text(
                text_position,
                label,
                fill=color[i] if isinstance(color, list) else color,
                font=label_font
            )

    return image

def get_name_from_path(path):
    return os.path.basename(path).split(".")[0]

def load_pdf(pdf_path, page_range: List[int] | None = None, dpi=IMAGE_DPI):
    doc = pypdfium2.PdfDocument(pdf_path)
    last_page = len(doc)

    if page_range:
        page_range = [p - 1 for p in page_range]  # shift to 0-based
        assert all([0 <= page < last_page for page in page_range]), f"Invalid page range: {page_range}"
    else:
        page_range = list(range(last_page))

    images = [doc[i].render(scale=IMAGE_DPI/72, draw_annots=False).to_pil() for i in page_range]
    images = [image.convert("RGB") for image in images]
    doc.close()
    return images

def load_image(image_path):
    image = Image.open(image_path).convert("RGB")
    return [image]

def containment_score(master, child):
    xA = max(master[0], child[0])
    yA = max(master[1], child[1])
    xB = min(master[2], child[2])
    yB = min(master[3], child[3])

    inter_area = max(0, xB - xA) * max(0, yB - yA)
    child_area = (child[2] - child[0]) * (child[3] - child[1])

    if child_area == 0:
        return 0.0

    return inter_area / child_area

def match_and_merge_bboxes(dict_a, dict_b, dict_c, containment_threshold=0.4):
    merged_dict = deepcopy(dict_a)

    for file_key in merged_dict:
        if file_key not in dict_b:
            continue

        for page_index, page_a in enumerate(merged_dict[file_key]):
            if page_index >= len(dict_b[file_key]):
                continue

            bboxes = page_a.get("bboxes", [])
            text_lines = dict_b[file_key][page_index].get("text_lines", [])
            if not text_lines or not bboxes:
                continue

            # Compute centers of text lines
            text_centers = np.array([
                [(tl["bbox"][0] + tl["bbox"][2]) / 2, (tl["bbox"][1] + tl["bbox"][3]) / 2]
                for tl in text_lines
            ])  # Shape: (N, 2)

            for bbox_entry in bboxes:
                if bbox_entry.get("label", "") in {"Table", "Table-of-contents"}:
                    bbox_entry["table_content"] = dict_c[file_key].pop(0)
                    cells = bbox_entry["table_content"].get("cells", [])

                    for cell in cells:
                        adjusted_bbox = cell.get("adjusted_bbox", [])
                        if not adjusted_bbox:
                            continue

                        x_min, y_min, x_max, y_max = adjusted_bbox
                        # Vectorized check for text line centers inside cell
                        inside = (
                            (text_centers[:, 0] > x_min) & (text_centers[:, 0] < x_max) &
                            (text_centers[:, 1] > y_min) & (text_centers[:, 1] < y_max)
                        )
                        matching_indices = np.where(inside)[0]
                        matching_texts = [text_lines[i]["text"] for i in matching_indices]
                        cell["text"] = " ".join(matching_texts) if matching_texts else ""
                else:
                    bbox = bbox_entry.get("bbox", [])
                    if not bbox:
                        continue

                    x_min, y_min, x_max, y_max = bbox
                    # Vectorized check for text line centers inside bbox
                    inside = (
                        (text_centers[:, 0] > x_min) & (text_centers[:, 0] < x_max) &
                        (text_centers[:, 1] > y_min) & (text_centers[:, 1] < y_max)
                    )
                    matching_indices = np.where(inside)[0]
                    bbox_entry["text_lines"] = [text_lines[i] for i in matching_indices]

    return merged_dict

def adjust_bbox_to_original_size(bbox1, bbox2):
    x_offset, y_offset = int(bbox1[0]), int(bbox1[1])
    return [
        int(bbox2[0] + x_offset),
        int(bbox2[1] + y_offset),
        int(bbox2[2] + x_offset),
        int(bbox2[3] + y_offset),
    ]

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def handle_table(table_obj, current_page):
    cells = table_obj.get("table_content", {}).get("cells", [])
    if not cells:
        return ""

    # Organize cells into a dict[row_id][col_id] = text
    table = defaultdict(dict)
    max_row = 0
    max_col = 0

    for cell in cells:
        row = cell.get("row_id")
        col = cell.get("col_id")
        text = cell.get("text", "").strip().replace("\n", " ")
        table[row][col] = text
        max_row = max(max_row, row)
        max_col = max(max_col, col)

    # Build the table as a list of CSV rows
    csv_lines = []

    for r in range(max_row + 1):
        row = []
        for c in range(max_col + 1):
            cell_text = table[r].get(c, "")
            # Escape double quotes
            cell_text = cell_text.replace('"', '""')
            # Wrap in double quotes if it contains comma or quote
            if ',' in cell_text or '"' in cell_text:
                cell_text = f'"{cell_text}"'
            row.append(cell_text)
        csv_lines.append(",".join(row))

    csv_content = "\n".join(csv_lines)
    return f"<@Table>{csv_content}</@Table> "

def extract_texts_grouped_by_page(data):
    page_texts = defaultdict(str)
    word_count = [0]  # Use list for mutability inside nested function

    for pdf_name, pdf_content in data.items():
        for page_dict in pdf_content:
            current_page = f"{pdf_name}↳{page_dict.get('page', '')}"

            bboxes = page_dict.get("bboxes", [])
            for layout in bboxes:
                if layout.get("label") in ("Table", "Table-of-contents"):
                    table_data = handle_table(layout, current_page)
                    page_texts[current_page] += table_data + "\n"
                    word_count[0] += len(table_data.split())
                else:
                    for line in layout.get('text_lines', []):
                        if 'text' in line:
                            cleaned = clean_text(line['text'])
                            page_texts[current_page] += cleaned + " "
                            word_count[0] += len(cleaned.split())

    return page_texts, word_count[0]

def run_ocr_on_gpu(gpu_id, file_path, pdf_name, output_dir, debug, save_images, page_range=None):
    """
    Processes OCR on a given PDF using the models that were initialized
    once per worker process. Loads the PDF/image within this function to save memory.
    """
    global worker_gpu, det_predictor, layout_predictor, rec_predictor, table_rec_predictor, foundation_predictor

    # Ensure that the worker's GPU matches the expected one.
    if worker_gpu != gpu_id:
        torch.cuda.set_device(gpu_id)
        
    if debug:
        start = time.time()
        
    input_type = filetype.guess(file_path)
    if input_type and input_type.extension == "pdf":
        pdf_images_lowres = load_pdf(file_path, page_range, dpi=IMAGE_DPI)                # Use 96 DPI for layout and detection
        pdf_images_highres = load_pdf(file_path, page_range, dpi=IMAGE_DPI_HIGHRES)        # Use 192 DPI for recognition and table prediction
    elif input_type and input_type.extension in {"jpg", "jpeg", "png"}:
        single_image = load_image(file_path)
        pdf_images_lowres = single_image                                                # Simulate both lowres and highres by duplicating
        pdf_images_highres = single_image
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    ################################################### Layout Analysis ##################################################

    num_pages = len(pdf_images_lowres)
    layout_predictions_by_image = layout_predictor(pdf_images_lowres)

    layout_preds = defaultdict(list)
    for pred, img in zip(layout_predictions_by_image, pdf_images_lowres):
        out_pred = pred.model_dump()
        out_pred["page"] = len(layout_preds[pdf_name]) + 1

        # save {Figure, Picture} figures found while OCR
        save_images_dir = f"{output_dir}/assets/{pdf_name}"
        os.makedirs(save_images_dir, exist_ok=True)
        for l in out_pred["bboxes"]:
            if l["label"] in ["Picture", "Figure"]:
                bb = l["bbox"]  # [x_min, y_min, x_max, y_max]
                label = l["label"]
                position = l["position"]

                cropped_img = img.crop(bb)
                cropped_img.save(os.path.join(save_images_dir, f"{out_pred['page']}_{label}_{position}.png"))

        layout_preds[pdf_name].append(out_pred)

    if save_images:
        save_images_dir = f"{output_dir}/images/layout/{pdf_name}"
        os.makedirs(save_images_dir, exist_ok=True)
        for idx, (image, layout_pred) in enumerate(zip(pdf_images_lowres, layout_predictions_by_image)):
            polygons = [p.polygon for p in layout_pred.bboxes]
            labels = [f"{p.label}-{p.position}" for p in layout_pred.bboxes]
            bbox_image = draw_polys_on_image(polygons, deepcopy(image), labels=labels, color='red')
            bbox_image.save(os.path.join(save_images_dir, f"{idx}_layout.png"))

    if debug:
        debug_results_dir = f"{output_dir}/debug"
        os.makedirs(debug_results_dir, exist_ok=True)
        output_path = os.path.join(debug_results_dir, f"{pdf_name}_layout.json")
        with open(output_path, "w+", encoding="utf-8") as f:
            json.dump(layout_preds, f, ensure_ascii=False)

    ################################################### Detection ##################################################

    detection_by_image = det_predictor(pdf_images_lowres)

    det_preds = defaultdict(list)
    bboxes = []
    for pred in detection_by_image:
        out_pred = pred.model_dump()
        out_pred["page"] = len(det_preds[pdf_name]) + 1
        det_preds[pdf_name].append(out_pred)
        bboxes.append([item['bbox'] for item in out_pred['bboxes']])

    if save_images:
        save_images_dir = f"{output_dir}/images/bboxes/{pdf_name}"
        os.makedirs(save_images_dir, exist_ok=True)
        for idx, (image, pred) in enumerate(zip(pdf_images_lowres, detection_by_image)):
            polygons = [p.polygon for p in pred.bboxes]
            bbox_image = draw_polys_on_image(polygons, deepcopy(image), color='blue')
            bbox_image.save(os.path.join(save_images_dir, f"{idx}_bbox.png"))

        save_images_dir = f"{output_dir}/images/layout_w_bbox/{pdf_name}"
        os.makedirs(save_images_dir, exist_ok=True)
        for idx, (image, layout_pred) in enumerate(zip(pdf_images_lowres, layout_predictions_by_image)):
            polygons = [p.polygon for p in layout_pred.bboxes]
            labels = [f"{p.label}-{p.position}" for p in layout_pred.bboxes]
            bbox_image = draw_polys_on_image(polygons, deepcopy(image), labels=labels, color='red')

            for idx2, (image, pred) in enumerate(zip(pdf_images_lowres, detection_by_image)):
                if idx == idx2:
                    polygons = [p.polygon for p in pred.bboxes]
                    bbox_image = draw_polys_on_image(polygons, deepcopy(bbox_image), color='blue')
                    bbox_image.save(os.path.join(save_images_dir, f"{idx}_layout_w_bbox.png"))

    ################################################### Text Recognition ##################################################

    # Use the new Surya API with foundation predictor
    recognition_by_image = rec_predictor(
        pdf_images_highres,
        task_names=[TaskNames.ocr_with_boxes] * len(pdf_images_highres),
        det_predictor=det_predictor,
        highres_images=pdf_images_highres,
        math_mode=True
    )

    rec_preds = defaultdict(list)
    for pred in recognition_by_image:
        out_pred = pred.model_dump()
        out_pred["page"] = len(rec_preds[pdf_name]) + 1
        # Aggregate page-level confidence from text_lines only
        text_lines = out_pred.get("text_lines", [])
        if text_lines:
            total_conf = sum(line.get("confidence", 0.0) for line in text_lines)
            avg_conf = total_conf / len(text_lines)
        else:
            avg_conf = 0.0
        out_pred["page_confidence"] = avg_conf  # Add aggregated confidence
        rec_preds[pdf_name].append(out_pred)

    if save_images:
        save_images_dir = f"{output_dir}/images/text/{pdf_name}"
        os.makedirs(save_images_dir, exist_ok=True)
        for idx, (image, pred) in enumerate(zip(pdf_images_highres, recognition_by_image)):
            bboxes = [l.bbox for l in pred.text_lines]
            pred_text = [l.text for l in pred.text_lines]
            page_image = draw_text_on_image(bboxes, pred_text, image.size)
            page_image.save(os.path.join(save_images_dir, f"{idx}_text.png"))

    if debug:
        debug_results_dir = f"{output_dir}/debug"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(debug_results_dir, f"{pdf_name}_text.json")
        with open(output_path, "w+", encoding="utf-8") as f:
            json.dump(rec_preds, f, ensure_ascii=False)

    ################################################### Table Layout Recognition ##################################################

    table_imgs = []
    table_counts = []
    table_bboxes = []
    for layout_pred, img in zip(layout_predictions_by_image, pdf_images_highres):
        bbox = [l.bbox for l in layout_pred.bboxes if l.label in ["Table", "Table-of-contents"]]
        table_bboxes.append(bbox)
        table_counts.append(len(bbox))

        if len(bbox) == 0:
            continue

        page_table_imgs = []
        for bb in bbox:
            page_table_imgs.append(img.crop(bb))

        table_imgs.extend(page_table_imgs)

    if table_imgs:
        table_layout_predictions_by_image = table_rec_predictor(table_imgs)

        page_idx = 0
        prev_count = 0
        table_layout_preds = defaultdict(list)
        for i in range(sum(table_counts)):
            while i >= prev_count + table_counts[page_idx]:
                prev_count += table_counts[page_idx]
                page_idx += 1

            pred = table_layout_predictions_by_image[i]
            table_img = table_imgs[i]

            out_pred = pred.model_dump()
            out_pred["page"] = page_idx
            table_idx = i - prev_count
            out_pred["table_idx"] = table_idx
            out_pred["adjusted_image_bbox"] = adjust_bbox_to_original_size(table_bboxes[page_idx][table_idx], out_pred["image_bbox"])
            for cell in out_pred["cells"]:
                cell["adjusted_bbox"] = adjust_bbox_to_original_size(table_bboxes[page_idx][table_idx], cell['bbox'])
            out_pred.pop("unmerged_cells", None)
            for row in out_pred["rows"]:
                row["adjusted_bbox"] = adjust_bbox_to_original_size(table_bboxes[page_idx][table_idx], row['bbox'])
            for col in out_pred["cols"]:
                col["adjusted_bbox"] = adjust_bbox_to_original_size(table_bboxes[page_idx][table_idx], col['bbox'])
            table_layout_preds[pdf_name].append(out_pred)

            if save_images:
                save_images_dir = f"{output_dir}/images/table/{pdf_name}"
                os.makedirs(save_images_dir, exist_ok=True)

                rows = [l.bbox for l in pred.rows]
                cols = [l.bbox for l in pred.cols]
                cells = [l.bbox for l in pred.cells]
                row_labels = [f"Row {l.row_id}" for l in pred.rows]
                col_labels = [f"Col {l.col_id}" for l in pred.cols]

                rc_image = deepcopy(table_img)
                rc_image = draw_bboxes_on_image(rows, rc_image, labels=row_labels, label_font_size=20, color="blue")
                rc_image = draw_bboxes_on_image(cols, rc_image, labels=col_labels, label_font_size=20, color="red")
                rc_image.save(os.path.join(save_images_dir, f"{page_idx}_table{table_idx}_rc.png"))

                cell_image = deepcopy(table_img)
                cell_image = draw_bboxes_on_image(cells, cell_image, color="green")
                cell_image.save(os.path.join(save_images_dir, f"{page_idx}_table{table_idx}_cells.png"))

                rescaled_image = Image.new("RGB", pdf_images_highres[page_idx].size, color="white")
                rescaled_image = draw_bboxes_on_image([out_pred["adjusted_image_bbox"]], rescaled_image, labels=[f"Table {table_idx}"], label_font_size=20, color="red")
                rescaled_image.save(os.path.join(save_images_dir, f"{page_idx}_table{table_idx}_rescaled.png"))
                
                adjusted_cells = [c["adjusted_bbox"] for c in out_pred["cells"]]
                if table_idx == 0:  
                    all_tables_rescaled_image = Image.new("RGB", pdf_images_highres[page_idx].size, color="white")
                if all_tables_rescaled_image:
                    all_tables_rescaled_image = draw_bboxes_on_image([out_pred["adjusted_image_bbox"]], all_tables_rescaled_image, labels=[f"Table {table_idx}"], label_font_size=20, color="red")
                    all_tables_rescaled_image = draw_bboxes_on_image(adjusted_cells, all_tables_rescaled_image, color="green")
                if all_tables_rescaled_image and table_idx == table_counts[page_idx] - 1:   
                    all_tables_rescaled_image.save(os.path.join(save_images_dir, f"{page_idx}_all_tables_rescaled.png"))

        if debug:
            debug_results_dir = f"{output_dir}/debug"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(debug_results_dir, f"{pdf_name}_tables.json")
            with open(output_path, "w+", encoding="utf-8") as f:
                json.dump(table_layout_preds, f, ensure_ascii=False)
    else:
        table_layout_preds = defaultdict(list)

    ################################################### Merging it all ##################################################

    # Compute document-level confidence
    for pdf_name, pages in rec_preds.items():
        page_confidences = [page["page_confidence"] for page in pages]
        if page_confidences:
            doc_conf = sum(page_confidences) / len(page_confidences)
        else:
            doc_conf = 0.0

    mergerd_preds = match_and_merge_bboxes(layout_preds, rec_preds, table_layout_preds)

    output_dir_w_layout = f"{output_dir}/with_layout"
    os.makedirs(output_dir_w_layout, exist_ok=True)
    output_path = os.path.join(output_dir_w_layout, f"{pdf_name}.json")
    with open(output_path, "w+", encoding="utf-8") as f:
        json.dump(mergerd_preds, f, ensure_ascii=False)
    
    raw_text, word_count = extract_texts_grouped_by_page(mergerd_preds)

    output_dir_raw = f"{output_dir}/raw"
    os.makedirs(output_dir_raw, exist_ok=True)
    output_path = os.path.join(output_dir_raw, f"{pdf_name}_raw_text.json")
    with open(output_path, "w+", encoding="utf-8") as f:
        json.dump(raw_text , f, ensure_ascii=False)

    if debug:
        print(f"OCR for {pdf_name} took {time.time() - start:.2f} seconds")

    del pdf_images_lowres
    del pdf_images_highres
    gc.collect()

    return word_count, num_pages, doc_conf

def init_worker(gpu_id):
    """
    Initializer function for each worker process.
    Loads the models once and sets the GPU device.
    """
    global worker_gpu, det_predictor, layout_predictor, rec_predictor, table_rec_predictor, foundation_predictor
    
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')  # Suppress stdout temporarily

    try:
        worker_gpu = gpu_id
        torch.cuda.set_device(worker_gpu)

        # Initialize foundation predictor first
        foundation_predictor = FoundationPredictor()
        
        # Initialize all predictors correctly
        det_predictor = DetectionPredictor()
        layout_predictor = LayoutPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        table_rec_predictor = TableRecPredictor()

        # Disable tqdm progress bars
        det_predictor.disable_tqdm = True
        layout_predictor.disable_tqdm = True
        rec_predictor.disable_tqdm = True
        table_rec_predictor.disable_tqdm = True

    except torch.cuda.OutOfMemoryError as e:
        sys.stdout = original_stdout
        tqdm.write(f"[Worker {gpu_id}] CUDA Out Of Memory during initialization: {e}")
        raise RuntimeError(f"Worker {gpu_id} failed to initialize due to OOM.") from e

    except Exception as e:
        sys.stdout = original_stdout
        tqdm.write(f"[Worker {gpu_id}] Unexpected error during initialization: {e}")

    finally:
        sys.stdout.close()
        sys.stdout = original_stdout

def update_checkpoint(checkpoint_path, identifier_w_pdf_name, status="done", word_count=None, doc_conf=0.0, error=None, num_pages=None, time_taken=None):
    """
    Update the checkpoint JSON file safely with a file lock and atomic write.
    """
    lock_path = checkpoint_path + ".lock"
    with FileLock(lock_path):
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError(f"Corrupted checkpoint file detected: {checkpoint_path}. Please resolve the issue.")
        else:
            data = {}

        data[identifier_w_pdf_name] = {
            "status": status,
            "word count": word_count,
            "num pages": num_pages,
            "document-level confidence": doc_conf,
            "time taken (s)": time_taken,
            "timestamp": time.strftime("%d-%m-%YT%H:%M:%S", time.localtime()),
            "error": error
        }

        with open(checkpoint_path, "w") as f:
            json.dump(data, f, indent=2)

def worker_process(gpu_id, file_paths, input_dir, output_dir, debug, save_images, progress_counter, checkpoint_path, model_ready_event, page_range=None):
    """
    Worker process that initializes models once and then processes
    multiple PDFs assigned to this GPU.
    """
    init_worker(gpu_id)
    model_ready_event.set()  # Notify the main process that model is loaded
    
    for file_path in file_paths:
        identifier_w_pdf_name = re.sub(r'\.[^.]+$', '', file_path.removeprefix(f"{input_dir}/")).replace("/", "↳")
        start_time_pdf = time.time()

        try:
            word_count, num_pages, doc_conf = run_ocr_on_gpu(gpu_id, file_path, identifier_w_pdf_name, output_dir, debug, save_images, page_range)
            time_taken_pdf = time.time() - start_time_pdf
            update_checkpoint(checkpoint_path, identifier_w_pdf_name, status="done", word_count=word_count, num_pages=num_pages, doc_conf=doc_conf, time_taken=time_taken_pdf)
        except Exception as e:
            time_taken_pdf = time.time() - start_time_pdf
            update_checkpoint(checkpoint_path, identifier_w_pdf_name, status="error", error=str(e), time_taken=time_taken_pdf)

        with progress_counter.get_lock():
            progress_counter.value += 1

def parse_range_str(range_str: str) -> List[int]:
    range_lst = range_str.split(",")
    page_lst = []
    for i in range_lst:
        if "-" in i:
            start, end = i.split("-")
            page_lst += list(range(int(start), int(end) + 1))
        else:
            page_lst.append(int(i))
    return sorted(set(page_lst))

def main():
    parser = argparse.ArgumentParser(description="OCR text processing.")
    parser.add_argument("-i", "--input_path", type=str, required=True, help="Input path to files or folder.")
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="Directory to save output.")
    parser.add_argument("-g", "--gpus", type=str, help="Comma-separated list of GPU IDs to use.", required=True)
    parser.add_argument("-p", "--page_range", type=str, default=None, help="Page range to convert, specify comma-separated page numbers or ranges.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode.", default=False)
    parser.add_argument("-s", "--save-images", action="store_true", help="Save images of detected bboxes.", default=False)

    args = parser.parse_args()

    # Load checkpoint file to skip already processed files
    checkpoint_path = os.path.join(args.output_dir, "checkpoint.json")
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            try:
                checkpoint_data = json.load(f)
            except json.JSONDecodeError:
                raise ValueError(f"Corrupted checkpoint file detected: {checkpoint_path}. Please resolve the issue.")
    else:
        checkpoint_data = {}

    already_done = {pdf_path for pdf_path, info in checkpoint_data.items() if info.get("status") == "done"}

    # Parse page range if provided
    if args.page_range:
        page_range = parse_range_str(args.page_range)
    else:
        page_range = None

    file_paths = []
    num_files_already_done = 0

    if os.path.isdir(args.input_path):
        spinner = "|/-\\"
        spin_idx = 0
        # First, gather all non-hidden files to get total count for tqdm
        all_files = []
        for root, dirs, files in os.walk(args.input_path):
            print(f"Scanning all directories for files... {spinner[spin_idx % len(spinner)]}", end="\r")
            spin_idx += 1
            for file in files:
                if not file.startswith("."):
                    all_files.append(os.path.join(root, file))

        for path in tqdm(all_files, desc="Filtering valid files", dynamic_ncols=True):
            extension = filetype.guess(path)

            if extension and extension.extension in {'pdf', 'jpg', 'jpeg', 'png'}:
                identifier_w_pdf_name = re.sub(r'\.[^.]+$', '', path.removeprefix(f"{args.input_path}/")).replace("/", "↳")
                if identifier_w_pdf_name in already_done:
                    num_files_already_done += 1
                    continue
                file_paths.append(path)

        num_files_to_process = len(file_paths)
        num_total_files_scanned = num_files_to_process + num_files_already_done

        if not file_paths:
            print(f"Total files scanned: {num_total_files_scanned}, out of which {num_files_already_done} are already processed.")
            return
    else:
        # Single file case
        input_type = filetype.guess(args.input_path)
        identifier_w_pdf_name = re.sub(r'\.[^.]+$', '', args.input_path.removeprefix(f"{args.input_path}/")).replace("/", "↳")

        if identifier_w_pdf_name in already_done:
            num_files_already_done = 1
            num_files_to_process = 0
            num_total_files_scanned = 1
            return

        elif input_type and input_type.extension in {"pdf", "jpg", "jpeg", "png"}:
            file_paths.append(args.input_path)
            num_files_to_process = 1
            num_files_already_done = 0
            num_total_files_scanned = 1
        else:
            print(f"Unsupported file type: {args.input_path}")
            return

    if args.gpus.lower() == "all":
        gpu_ids = list(range(torch.cuda.device_count()))
    else:
        gpu_ids = [int(gpu_id) for gpu_id in args.gpus.split(",")]

    # Create a mapping: for each GPU, assign the file paths (round-robin)
    path_gpu_mapping = {gpu: [] for gpu in gpu_ids}
    for i, file_path in tqdm(enumerate(file_paths), total=len(file_paths), desc="Distributing files across GPUs", dynamic_ncols=True):
        gpu_id = gpu_ids[i % len(gpu_ids)]
        path_gpu_mapping[gpu_id].append(file_path)

    os.makedirs(args.output_dir, exist_ok=True)

    # Start resource monitoring here
    start_resource_monitoring(gpu_ids)

    # Set up a shared counter for overall progress
    progress_counter = Value('i', 0)

    # Create a separate process for each GPU to ensure model reusability
    processes = []
    model_ready_events = []
    for gpu_id in gpu_ids:
        paths_for_gpu = path_gpu_mapping[gpu_id]
        if not paths_for_gpu:
            continue

        model_ready_event = Event()
        model_ready_events.append(model_ready_event)

        p = Process(
            target=worker_process,
            args=(gpu_id, paths_for_gpu, args.input_path, args.output_dir, args.debug, args.save_images,
                progress_counter, checkpoint_path, model_ready_event, page_range)
        )
        processes.append(p)
        p.start()

    gpu_init_pbar = tqdm(total=len(model_ready_events), desc="Initializing models on GPUs", dynamic_ncols=True)

    # Wait for each worker to finish model loading
    for event in model_ready_events:
        event.wait()
        gpu_init_pbar.update(1)

    gpu_init_pbar.close()

    # Use tqdm to show an overall progress bar
    with tqdm(total=num_total_files_scanned, initial=num_files_already_done, desc="Overall Progress", dynamic_ncols=True) as pbar:
        last_val = 0  # Only track new progress; already done was given in initial=...

        # Poll until all processes are complete
        while any(p.is_alive() for p in processes):
            with progress_counter.get_lock():
                current_val = progress_counter.value
            pbar.update(current_val - last_val)
            last_val = current_val
            time.sleep(0.5)

        # Final update after all processes have finished
        with progress_counter.get_lock():
            current_val = progress_counter.value
        pbar.update(current_val - last_val)

    # Ensure all processes have finished
    for p in processes:
        p.join()

    # Print total word count
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            data = json.load(f)
        print("Total word count across all checkpoints:", sum(entry.get("word count", 0) for entry in data.values() if entry.get("word count") is not None))
        total_time = sum(d["time taken (s)"] for d in data.values() if d["status"] == "done" and d["error"] is None)
        total_pages = sum(d["num pages"] for d in data.values() if d["status"] == "done" and d["error"] is None)
        if total_pages > 0:
            avg_time_per_page = total_time / total_pages
            print(f"Average time per page: {avg_time_per_page:.2f} seconds")
        else:
            print("No pages processed successfully, cannot compute average time.")

if __name__ == "__main__":
    set_start_method('spawn', force=True)
    start_time = time.time()
    main()

    safe_avg = lambda total, count: total / count if count > 0 else 0.0

    print(f"Average CPU usage: {safe_avg(resource_stats['cpu_sum'], resource_stats['cpu_count']):.2f}%")
    print(f"Average RAM usage: {safe_avg(resource_stats['ram_sum'], resource_stats['ram_count']):.2f} MB")
    print(f"Average GPU usage: {safe_avg(resource_stats['gpu_util_sum'], resource_stats['gpu_util_count']):.2f}%")
    print(f"Average VRAM usage: {safe_avg(resource_stats['gpu_mem_sum'], resource_stats['gpu_mem_count']):.2f} MB")

    print(f"\nTotal execution time for this session: {time.time() - start_time:.2f} seconds")
