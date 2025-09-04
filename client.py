# client.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
import threading
import os 
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

SERVER_URL = "http://127.0.0.1:5000"

class VideoUploaderClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cliente de Processamento de Vídeo")
        self.geometry("900x700")

        # --- Estilo ---
        style = ttk.Style(self)
        style.theme_use('clam') # Um tema mais moderno

        # --- Layout Principal com Grid ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # --- Frame de Upload ---
        upload_frame = ttk.LabelFrame(self, text="Enviar Novo Vídeo", padding="10")
        upload_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        upload_frame.columnconfigure(0, weight=1)
        
        self.filepath_label = ttk.Label(upload_frame, text="Nenhum arquivo selecionado...", anchor="w")
        self.filepath_label.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.select_button = ttk.Button(upload_frame, text="Selecionar Vídeo", command=self.select_file)
        self.select_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Novos filtros
        filters = ["grayscale", "canny", "sepia", "pixelate", "invert"]
        self.filter_var = tk.StringVar(value=filters[0])
        self.filter_menu = ttk.Combobox(upload_frame, textvariable=self.filter_var, values=filters, state="readonly")
        self.filter_menu.grid(row=0, column=2, padx=5, pady=5)

        self.upload_button = ttk.Button(upload_frame, text="Enviar e Processar", command=self.start_upload_thread)
        self.upload_button.grid(row=0, column=3, padx=5, pady=5)
        
        self.filepath = ""

        # --- Frame de Histórico ---
        history_frame = ttk.LabelFrame(self, text="Histórico de Vídeos", padding="10")
        history_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        
        columns = ("id", "original_name", "filter", "size", "created_at")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings")
        
        self.history_tree.heading("id", text="UUID")
        self.history_tree.heading("original_name", text="Nome")
        self.history_tree.heading("filter", text="Filtro")
        self.history_tree.heading("size", text="Tamanho")
        self.history_tree.heading("created_at", text="Data")
        
        self.history_tree.column("id", width=250)
        self.history_tree.column("original_name", width=150)
        self.history_tree.column("filter", width=80, anchor="center")
        self.history_tree.column("size", width=80, anchor="e")
        self.history_tree.column("created_at", width=150)
        
        self.history_tree.grid(row=0, column=0, columnspan=2, sticky="nsew")
        
        # Botões do Histórico
        self.refresh_button = ttk.Button(history_frame, text="Atualizar", command=self.load_history)
        self.refresh_button.grid(row=1, column=0, pady=10, sticky="e")
        
        self.delete_button = ttk.Button(history_frame, text="Excluir Selecionado", command=self.delete_selected_video)
        self.delete_button.grid(row=1, column=1, padx=5, pady=10, sticky="w")

        # --- Frame de Status (com Barra de Progresso) ---
        status_frame = ttk.LabelFrame(self, text="Status", padding="10")
        status_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=5)
        
        self.status_label = ttk.Label(status_frame, text="Pronto.", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        self.load_history()

    def select_file(self):
        filepath = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=(("Vídeos", "*.mp4 *.avi *.mov"), ("Todos os arquivos", "*.*"))
        )
        if filepath:
            self.filepath = filepath
            self.filepath_label.config(text=os.path.basename(filepath))

    def start_upload_thread(self):
        if not self.filepath:
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo de vídeo primeiro.")
            return
        # Desabilita botões para evitar ações concorrentes
        self.upload_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.DISABLED)
        
        # Inicia o upload em uma thread separada para não travar a GUI
        upload_thread = threading.Thread(target=self.upload_video)
        upload_thread.start()
        
    def upload_video(self):
        self.status_label.config(text="Iniciando upload...")
        self.progress_bar['value'] = 0
        
        url = f"{SERVER_URL}/upload"
        filter_choice = self.filter_var.get()
        
        try:
            filename = os.path.basename(self.filepath)
            encoder = MultipartEncoder(
                fields={
                    'filter': filter_choice,
                    'video': (filename, open(self.filepath, 'rb'), 'video/mp4')
                }
            )
            
            # Monitor para acompanhar o progresso do upload
            monitor = MultipartEncoderMonitor(encoder, self.upload_progress_callback)
            
            headers = {'Content-Type': monitor.content_type}
            response = requests.post(url, data=monitor, headers=headers, timeout=300)
            
            response.raise_for_status()
            result = response.json()
            
            self.status_label.config(text=f"Sucesso: {result.get('message')}")
            self.after(500, self.load_history)
            
        except requests.exceptions.RequestException as e:
            self.status_label.config(text=f"Erro de Conexão: {e}")
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor: {e}")
        except Exception as e:
            self.status_label.config(text=f"Erro: {e}")
            messagebox.showerror("Erro", f"Ocorreu um erro inesperado: {e}")
        finally:
            # Reabilita os botões na thread principal
            self.after(0, self.enable_buttons)
            self.progress_bar['value'] = 0

    def upload_progress_callback(self, monitor):
        progress = (monitor.bytes_read / monitor.len) * 100
        self.progress_bar['value'] = progress
        self.status_label.config(text=f"Enviando... {progress:.1f}%")
        
    def enable_buttons(self):
        self.upload_button.config(state=tk.NORMAL)
        self.select_button.config(state=tk.NORMAL)

    def format_bytes(self, size):
        if size is None: return "N/A"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G'}
        while size > power and n < len(power_labels):
            size /= power
            n += 1
        return f"{size:.1f}{power_labels[n]}B"

    def load_history(self):
        self.status_label.config(text="Atualizando histórico...")
        for i in self.history_tree.get_children():
            self.history_tree.delete(i)
        try:
            response = requests.get(f"{SERVER_URL}/videos")
            response.raise_for_status()
            videos = response.json()
            
            for video in videos:
                size_formatted = self.format_bytes(video.get('size_bytes'))
                self.history_tree.insert("", tk.END, values=(
                    video['id'], 
                    video['original_name'] + video['original_ext'], 
                    video['filter'], 
                    size_formatted, 
                    video['created_at'].split('T')[0]
                ))
            self.status_label.config(text="Histórico atualizado.")
        except requests.exceptions.RequestException:
            self.status_label.config(text="Erro ao carregar histórico.")

    def delete_selected_video(self):
        selected_items = self.history_tree.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Nenhum vídeo selecionado no histórico.")
            return

        selected_item = selected_items[0]
        video_id = self.history_tree.item(selected_item)['values'][0]
        
        if not messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o vídeo {video_id}?"):
            return
            
        try:
            response = requests.delete(f"{SERVER_URL}/video/{video_id}")
            response.raise_for_status()
            messagebox.showinfo("Sucesso", "Vídeo excluído com sucesso.")
            self.load_history() # Recarrega a lista
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível excluir o vídeo: {e}")

if __name__ == "__main__":
    app = VideoUploaderClient()
    app.mainloop()