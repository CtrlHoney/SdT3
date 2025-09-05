# server.py
import os
import uuid
import sqlite3
import cv2
import shutil
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

# --- Configuração ---
MEDIA_ROOT = "media"
INCOMING_PATH = os.path.join(MEDIA_ROOT, "incoming")
DB_FILE = "videos.db"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = INCOMING_PATH
app.config['MEDIA_ROOT'] = MEDIA_ROOT

# --- Funções de Processamento de Vídeo ---

def apply_filter_to_video(input_path, output_path, filter_func):
    """Estrutura base para aplicar uma função de filtro em cada frame de um vídeo."""
    cap = cv2.VideoCapture(input_path)
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height), isColor=True)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        processed_frame = filter_func(frame)
        
        if len(processed_frame.shape) == 2:
            processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)
            
        out.write(processed_frame)
        
    cap.release()
    out.release()

def filter_grayscale(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

def filter_canny_edge(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, 100, 200)

def filter_sepia(frame):
    kernel = np.array([[0.272, 0.534, 0.131],
                       [0.349, 0.686, 0.168],
                       [0.393, 0.769, 0.189]])
    sepia_frame = cv2.transform(frame, kernel)
    sepia_frame[np.where(sepia_frame > 255)] = 255
    return sepia_frame

def filter_pixelate(frame, pixel_size=12):
    h, w = frame.shape[:2]
    temp = cv2.resize(frame, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)

def filter_invert(frame):
    return cv2.bitwise_not(frame)

FILTERS = {
    'grayscale': filter_grayscale,
    'canny': filter_canny_edge,
    'sepia': filter_sepia,
    'pixelate': filter_pixelate,
    'invert': filter_invert
}

# --- Funções de Banco de Dados ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def save_metadata_to_db(video_data):
    """Salva os metadados no banco, agora incluindo path_thumbnail."""
    conn = get_db_connection()
    sql = ''' INSERT INTO videos(id, original_name, original_ext, mime_type, size_bytes, duration_sec, fps, width, height, filter, created_at, path_original, path_processed, path_thumbnail)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, tuple(video_data.values()))
    conn.commit()
    conn.close()

# --- Funções Auxiliares ---
def format_bytes(size):
    if size is None: return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels):
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}B"

# --- Rotas da API (Endpoints) ---

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"error": "Nenhum arquivo de vídeo enviado"}), 400
    
    file = request.files['video']
    filter_type = request.form.get('filter', 'grayscale')

    if file.filename == '':
        return jsonify({"error": "Nome de arquivo vazio"}), 400
    if filter_type not in FILTERS:
        return jsonify({"error": "Filtro inválido"}), 400

    if file:
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
        file.save(temp_path)
        
        video_uuid = str(uuid.uuid4())
        now = datetime.now()
        date_path = os.path.join(str(now.year), f"{now.month:02d}", f"{now.day:02d}")
        video_dir_rel = os.path.join(date_path, video_uuid)
        video_dir_abs = os.path.join(app.config['MEDIA_ROOT'], video_dir_rel)

        original_dir = os.path.join(video_dir_abs, "original")
        processed_dir = os.path.join(video_dir_abs, "processed", filter_type)
        thumbs_dir = os.path.join(video_dir_abs, "thumbs")
        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(thumbs_dir, exist_ok=True)

        final_original_path_rel = os.path.join(video_dir_rel, "original", f"video{ext}")
        final_original_path_abs = os.path.join(app.config['MEDIA_ROOT'], final_original_path_rel)
        os.rename(temp_path, final_original_path_abs)

        final_processed_path_rel = os.path.join(video_dir_rel, "processed", filter_type, f"video{ext}")
        final_processed_path_abs = os.path.join(app.config['MEDIA_ROOT'], final_processed_path_rel)
        apply_filter_to_video(final_original_path_abs, final_processed_path_abs, FILTERS[filter_type])

        cap = cv2.VideoCapture(final_original_path_abs)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Gera o caminho relativo e absoluto da thumbnail
        thumb_path_rel = os.path.join(video_dir_rel, "thumbs", "frame_0001.jpg")
        thumb_path_abs = os.path.join(app.config['MEDIA_ROOT'], thumb_path_rel)

        ret, frame = cap.read()
        if ret:
            cv2.imwrite(thumb_path_abs, frame)
        cap.release()
        
        video_data = {
            "id": video_uuid, "original_name": name, "original_ext": ext, "mime_type": file.mimetype,
            "size_bytes": os.path.getsize(final_original_path_abs), "duration_sec": round(duration, 2),
            "fps": round(fps, 2), "width": width, "height": height, "filter": filter_type,
            "created_at": now.isoformat(), "path_original": final_original_path_rel,
            "path_processed": final_processed_path_rel,
            "path_thumbnail": thumb_path_rel  # <-- CORREÇÃO: Adicionado ao dicionário
        }
        save_metadata_to_db(video_data)
        
        return jsonify({"success": True, "video_id": video_uuid, "message": "Vídeo processado com sucesso!"}), 201

    return jsonify({"error": "Falha no upload"}), 500

@app.route('/videos', methods=['GET'])
def get_videos():
    """Retorna a lista de todos os vídeos processados, com caminhos formatados para URL."""
    conn = get_db_connection()
    videos_from_db = conn.execute('SELECT * FROM videos ORDER BY created_at DESC').fetchall()
    conn.close()
    
    # CORREÇÃO: Formata os caminhos antes de enviar o JSON
    videos_list = []
    for video in videos_from_db:
        video_dict = dict(video)
        if video_dict.get('path_original'):
            video_dict['path_original'] = video_dict['path_original'].replace('\\', '/')
        if video_dict.get('path_processed'):
            video_dict['path_processed'] = video_dict['path_processed'].replace('\\', '/')
        if video_dict.get('path_thumbnail'):
            video_dict['path_thumbnail'] = video_dict['path_thumbnail'].replace('\\', '/')
        videos_list.append(video_dict)
        
    return jsonify(videos_list)

@app.route('/video/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Deleta um vídeo (arquivos e registro no banco)."""
    try:
        conn = get_db_connection()
        video = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
        
        if video is None:
            conn.close()
            return jsonify({"error": "Vídeo não encontrado"}), 404

        base_path_rel = os.path.dirname(os.path.dirname(video['path_original']))
        video_dir_abs = os.path.join(app.config['MEDIA_ROOT'], base_path_rel)
        
        if os.path.exists(video_dir_abs):
            shutil.rmtree(video_dir_abs)
        
        conn.execute('DELETE FROM videos WHERE id = ?', (video_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Vídeo deletado com sucesso"}), 200
    except Exception as e:
        print(f"Erro ao deletar vídeo {video_id}: {e}")
        return jsonify({"error": "Erro interno no servidor ao tentar deletar o vídeo."}), 500

@app.route('/gui')
def server_gui():
    """Renderiza a página web com o histórico de vídeos."""
    conn = get_db_connection()
    videos_data = conn.execute('SELECT * FROM videos ORDER BY created_at DESC').fetchall()
    conn.close()
    
    videos_for_template = []
    for video in videos_data:
        video_dict = dict(video)
        
        # Apenas formata os caminhos que já vêm do banco
        video_dict['path_original'] = video['path_original'].replace('\\', '/')
        if video_dict.get('path_processed'):
            video_dict['path_processed'] = video['path_processed'].replace('\\', '/')
        if video_dict.get('path_thumbnail'):
            video_dict['path_thumbnail'] = video['path_thumbnail'].replace('\\', '/')
        
        video_dict['formatted_size'] = format_bytes(video_dict.get('size_bytes'))
        video_dict['resolution'] = f"{video_dict.get('width')}x{video_dict.get('height')}"
        
        videos_for_template.append(video_dict)
        
    return render_template('index.html', videos=videos_for_template)

@app.route('/media/<path:filename>')
def serve_media(filename):
    """Serve os arquivos de mídia (vídeos, thumbnails) para o navegador."""
    return send_from_directory(app.config['MEDIA_ROOT'], filename)

# --- Bloco de Execução Principal ---
if __name__ == '__main__':
    os.makedirs(INCOMING_PATH, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)