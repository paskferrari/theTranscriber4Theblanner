#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Processor Server
Server Python per la trascrizione locale di documenti PDF, DOCX e TXT
"""

import os
import json
import uuid
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

import PyPDF2
import docx
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Directory per i file temporanei
TEMP_DIR = Path("temp_documents")
TEMP_DIR.mkdir(exist_ok=True)

# File JSON per i documenti trascritti
TRANSCRIPTS_FILE = "transcribed_documents.json"

class CompanyDataExtractor:
    """Classe per l'estrazione di informazioni anagrafiche aziendali da documenti"""
    
    def __init__(self):
        # Pattern regex per l'identificazione delle informazioni aziendali
        self.patterns = {
            'partita_iva': [
                r'PARTITA\s+IVA[\s\n]*([0-9]{11})',
                r'P\.?\s*IVA[:\s]*([0-9]{11})',
                r'Partita\s+IVA[:\s]*([0-9]{11})',
                r'P\.I\.[:\s]*([0-9]{11})',
                r'VAT[:\s]*([0-9]{11})'
            ],
            'codice_fiscale': [
                r'CODICE\s+FISCALE[\s\n]*([A-Z0-9]{11,16})',
                r'C\.?\s*F\.?[:\s]*([A-Z0-9]{11,16})',
                r'Codice\s+Fiscale[:\s]*([A-Z0-9]{11,16})',
                r'CF[:\s]*([A-Z0-9]{11,16})'
            ],
            'ragione_sociale': [
                # Pattern specifici per documenti Cribis
                r'Cribis\s+Check[\s\S]*?\n([A-Z][A-Z\s&\.]+(?:SPA|SRL|SNC|SAS|SRLS|S\.P\.A\.|S\.R\.L\.|S\.N\.C\.|S\.A\.S\.|S\.R\.L\.S\.)?)\n',
                r'Basic[\s\n]+([A-Z][A-Z\s&\.]+(?:SPA|SRL|SNC|SAS|SRLS|S\.P\.A\.|S\.R\.L\.|S\.N\.C\.|S\.A\.S\.|S\.R\.L\.S\.)?)\n',
                # Pattern generici
                r'Ragione\s+Sociale[:\s]*([^\n\r]+)',
                r'Denominazione[:\s]*([^\n\r]+)',
                r'Ditta[:\s]*([^\n\r]+)',
                r'Società[:\s]*([^\n\r]+)',
                # Pattern per nomi aziendali in maiuscolo
                r'\n([A-Z][A-Z\s&\.]+(?:SPA|SRL|SNC|SAS|SRLS|S\.P\.A\.|S\.R\.L\.|S\.N\.C\.|S\.A\.S\.|S\.R\.L\.S\.)?)\n'
            ],
            'sede_legale': [
                r'SEDE\s+LEGALE[\s\n]*([^\n\r]+)',
                r'Sede\s+legale[:\s]*([^\n\r]+)',
                r'CORSO\s+[A-Z\s]+[0-9]+[^\n\r]*',
                r'VIA\s+[A-Z\s]+[0-9]+[^\n\r]*',
                r'Indirizzo[:\s]*([^\n\r]+)',
                r'Domicilio[:\s]*([^\n\r]+)'
            ],
            'sede_amministrativa': [
                r'SEDE\s+AMMINISTRATIVA[\s\n]*([^\n\r]+)',
                r'Sede\s+amministrativa[:\s]*([^\n\r]+)'
            ],
            'cap': [
                r'CAP[:\s]*([0-9]{5})',
                r'\b([0-9]{5})\b'
            ],
            'citta': [
                r'Città[:\s]*([^\n\r,0-9]+)',
                r'Comune[:\s]*([^\n\r,0-9]+)',
                r'Località[:\s]*([^\n\r,0-9]+)',
                r'([0-9]{5})\s+([A-Z][A-Z\s]+)\s+\([A-Z]{2}\)'
            ],
            'provincia': [
                r'Provincia[:\s]*([A-Z]{2})',
                r'Prov\.?[:\s]*([A-Z]{2})',
                r'\(([A-Z]{2})\)'
            ],
            'telefono': [
                r'TELEFONO[\s\n]*([0-9]{10,})',
                r'Tel\.?[:\s]*([0-9\s\-\+\.\(\)]+)',
                r'Telefono[:\s]*([0-9\s\-\+\.\(\)]+)',
                r'Phone[:\s]*([0-9\s\-\+\.\(\)]+)'
            ],
            'fax': [
                r'FAX[\s\n]*([0-9]{10,})',
                r'Fax[:\s]*([0-9\s\-\+\.\(\)]+)'
            ],
            'email': [
                r'EMAIL[\s\n]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'E-mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'Email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            'email_certificata': [
                r'EMAIL\s+CERTIFICATA[\s\n]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            'sito_web': [
                r'SITO\s+WEB[\s\n]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'www\.\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            'natura_giuridica': [
                r'NATURA\s+GIURIDICA[\s\n]*([^\n\r]+)',
                r'Forma\s+giuridica[:\s]*([^\n\r]+)'
            ],
            'ateco': [
                r'ATECO\s+[0-9]{4}[\s\n]*([0-9]{6})\s+([^\n\r]+)',
                r'Codice\s+ATECO[:\s]*([0-9]{6})'
            ],
            'pec': [
                r'PEC[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'Posta\s+certificata[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            'rea': [
                r'REA[:\s]*([A-Z]{2}[\s\-]*[0-9]+)',
                r'Registro\s+Imprese[:\s]*([A-Z]{2}[\s\-]*[0-9]+)'
            ],
            'capitale_sociale': [
                r'Capitale\s+sociale[:\s]*€?\s*([0-9.,]+)',
                r'Cap\.\s+soc\.?[:\s]*€?\s*([0-9.,]+)',
                r'Capitale[:\s]*€?\s*([0-9.,]+)'
            ]
        }
    
    def extract_company_info(self, text):
        """Estrae le informazioni anagrafiche aziendali dal testo"""
        extracted_info = {}
        
        # Normalizza il testo per migliorare il matching
        normalized_text = self._normalize_text(text)
        
        # Estrae ogni tipo di informazione
        for info_type, patterns in self.patterns.items():
            extracted_info[info_type] = self._extract_field(normalized_text, patterns)
        
        # Post-processing per pulire e validare i dati
        extracted_info = self._clean_extracted_data(extracted_info)
        
        return extracted_info
    
    def _normalize_text(self, text):
        """Normalizza il testo per migliorare il pattern matching"""
        # Preserva le interruzioni di riga per i pattern specifici
        # ma normalizza spazi multipli sulla stessa riga
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\r', '\n', text)
        # Rimuove righe vuote multiple
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
    
    def _extract_field(self, text, patterns):
        """Estrae un campo specifico usando una lista di pattern"""
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if matches:
                # Se il match è una tupla (gruppi multipli), prendi il primo gruppo non vuoto
                if isinstance(matches[0], tuple):
                    for group in matches[0]:
                        if group and group.strip():
                            return group.strip()
                else:
                    # Restituisce il primo match trovato, pulito
                    return matches[0].strip()
        return None
    
    def _clean_extracted_data(self, data):
        """Pulisce e valida i dati estratti"""
        cleaned_data = {}
        
        for key, value in data.items():
            if value:
                if key == 'ragione_sociale':
                    # Pulisce la ragione sociale da parole non necessarie
                    cleaned_value = value
                    # Rimuove "Basic" e altre parole comuni nei documenti Cribis
                    cleaned_value = re.sub(r'^(Basic|Cribis Check|Report)\s+', '', cleaned_value, flags=re.IGNORECASE)
                    cleaned_value = re.sub(r'\s+(Basic|Cribis Check|Report)$', '', cleaned_value, flags=re.IGNORECASE)
                    cleaned_data[key] = cleaned_value.strip()
                elif key == 'partita_iva':
                    # Valida P.IVA (11 cifre)
                    cleaned_value = re.sub(r'[^0-9]', '', value)
                    if len(cleaned_value) == 11:
                        cleaned_data[key] = cleaned_value
                elif key == 'codice_fiscale':
                    # Valida CF (11 o 16 caratteri alfanumerici)
                    cleaned_value = re.sub(r'[^A-Z0-9]', '', value.upper())
                    if len(cleaned_value) in [11, 16]:
                        cleaned_data[key] = cleaned_value
                elif key == 'cap':
                    # Valida CAP (5 cifre)
                    cleaned_value = re.sub(r'[^0-9]', '', value)
                    if len(cleaned_value) == 5:
                        cleaned_data[key] = cleaned_value
                elif key == 'provincia':
                    # Valida provincia (2 lettere maiuscole)
                    cleaned_value = value.upper().strip()
                    if len(cleaned_value) == 2 and cleaned_value.isalpha():
                        cleaned_data[key] = cleaned_value
                elif key == 'email':
                    # Pulisce l'email rimuovendo caratteri non validi
                    cleaned_value = value.strip()
                    # Rimuove parole come EMAIL, MAIL, etc.
                    cleaned_value = re.sub(r'(EMAIL|MAIL|E-MAIL)\s*$', '', cleaned_value, flags=re.IGNORECASE)
                    # Rimuove testo dopo l'email se presente
                    cleaned_value = re.split(r'[\s,;]', cleaned_value)[0]
                    if '@' in cleaned_value and '.' in cleaned_value:
                        cleaned_data[key] = cleaned_value
                elif key == 'citta':
                    # Pulisce la città rimuovendo testo descrittivo
                    cleaned_value = value.strip()
                    # Se contiene frasi descrittive, non la considera valida
                    if not any(word in cleaned_value.lower() for word in ['sezione', 'contiene', 'dettaglio', 'numero', 'addetti']):
                        cleaned_data[key] = cleaned_value
                elif key == 'telefono':
                    # Pulisce il numero di telefono
                    cleaned_value = re.sub(r'[^0-9\+]', '', value)
                    if len(cleaned_value) >= 6:
                        cleaned_data[key] = cleaned_value
                elif key in ['email', 'pec']:
                    # Valida email/PEC
                    if '@' in value and '.' in value:
                        cleaned_data[key] = value.lower().strip()
                else:
                    # Per altri campi, rimuove spazi eccessivi
                    cleaned_value = re.sub(r'\s+', ' ', value).strip()
                    if cleaned_value:
                        cleaned_data[key] = cleaned_value
        
        return cleaned_data

class DocumentProcessor:
    def __init__(self):
        self.transcripts = self.load_transcripts()
        self.company_extractor = CompanyDataExtractor()
    
    def load_transcripts(self):
        """Carica i documenti trascritti dal file JSON"""
        if os.path.exists(TRANSCRIPTS_FILE):
            try:
                with open(TRANSCRIPTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Migra vecchia struttura se necessario
                    if "InfoBase" not in data:
                        data = {
                            "InfoBase": {
                                "extracted_companies": [],
                                "total_documents": len(data.get("documents", [])),
                                "last_updated": datetime.now().isoformat()
                            },
                            "documents": data.get("documents", []),
                            "session_id": data.get("session_id", str(uuid.uuid4()))
                        }
                    return data
            except:
                return {
                    "InfoBase": {
                        "extracted_companies": [],
                        "total_documents": 0,
                        "last_updated": datetime.now().isoformat()
                    },
                    "documents": [], 
                    "session_id": str(uuid.uuid4())
                }
        return {
            "InfoBase": {
                "extracted_companies": [],
                "total_documents": 0,
                "last_updated": datetime.now().isoformat()
            },
            "documents": [], 
            "session_id": str(uuid.uuid4())
        }
    
    def _update_info_base(self, company_info, filename):
        """Aggiorna InfoBase con le nuove informazioni aziendali"""
        if company_info and any(company_info.values()):
            # Crea un record per InfoBase
            company_record = {
                "source_document": filename,
                "extracted_at": datetime.now().isoformat(),
                "company_data": company_info
            }
            
            # Aggiunge alle aziende estratte
            self.transcripts["InfoBase"]["extracted_companies"].append(company_record)
            
        # Aggiorna i contatori
        self.transcripts["InfoBase"]["total_documents"] = len(self.transcripts["documents"])
        self.transcripts["InfoBase"]["last_updated"] = datetime.now().isoformat()
    
    def save_transcripts(self):
        """Salva i documenti trascritti nel file JSON"""
        with open(TRANSCRIPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.transcripts, f, ensure_ascii=False, indent=2)
    
    def extract_text_from_pdf(self, file_path):
        """Estrae testo da file PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise Exception(f"Errore nell'estrazione PDF: {str(e)}")
        return text.strip()
    
    def extract_text_from_docx(self, file_path):
        """Estrae testo da file DOCX"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Errore nell'estrazione DOCX: {str(e)}")
    
    def extract_text_from_txt(self, file_path):
        """Estrae testo da file TXT"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            # Prova con encoding diverso
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read().strip()
        except Exception as e:
            raise Exception(f"Errore nell'estrazione TXT: {str(e)}")
    
    def process_document(self, file_data, filename):
        """Processa un documento e ne estrae il testo"""
        # Salva il file temporaneamente
        file_id = str(uuid.uuid4())
        file_extension = Path(filename).suffix.lower()
        temp_file_path = TEMP_DIR / f"{file_id}{file_extension}"
        
        try:
            # Salva il file
            with open(temp_file_path, 'wb') as f:
                f.write(file_data)
            
            # Estrae il testo in base al tipo di file
            if file_extension == '.pdf':
                text = self.extract_text_from_pdf(temp_file_path)
            elif file_extension in ['.docx', '.doc']:
                text = self.extract_text_from_docx(temp_file_path)
            elif file_extension == '.txt':
                text = self.extract_text_from_txt(temp_file_path)
            else:
                raise Exception(f"Formato file non supportato: {file_extension}")
            
            # Estrae le informazioni aziendali dal testo
            company_info = self.company_extractor.extract_company_info(text)
            
            # Crea il documento trascritto
            document = {
                "id": file_id,
                "filename": filename,
                "text": text,
                "file_type": file_extension,
                "processed_at": datetime.now().isoformat(),
                "word_count": len(text.split()),
                "char_count": len(text),
                "company_info": company_info
            }
            
            # Aggiunge alla lista dei documenti
            self.transcripts["documents"].append(document)
            
            # Aggiorna InfoBase
            self._update_info_base(company_info, filename)
            
            self.save_transcripts()
            
            return document
            
        finally:
            # Rimuove il file temporaneo
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    def get_all_documents(self):
        """Restituisce tutti i documenti trascritti"""
        return self.transcripts["documents"]
    
    def remove_document(self, doc_id):
        """Rimuove un documento dalla lista"""
        self.transcripts["documents"] = [
            doc for doc in self.transcripts["documents"] 
            if doc["id"] != doc_id
        ]
        self.save_transcripts()
    
    def clear_session(self):
        """Pulisce tutti i documenti della sessione"""
        self.transcripts = {"documents": [], "session_id": str(uuid.uuid4())}
        self.save_transcripts()
        
        # Rimuove il file JSON
        if os.path.exists(TRANSCRIPTS_FILE):
            os.remove(TRANSCRIPTS_FILE)

# Inizializza il processore
processor = DocumentProcessor()

@app.route('/process_document', methods=['POST'])
def process_document():
    """Endpoint per processare un documento"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nessun file fornito"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nome file vuoto"}), 400
        
        # Processa il documento
        document = processor.process_document(file.read(), file.filename)
        
        return jsonify({
            "success": True,
            "document": {
                "id": document["id"],
                "filename": document["filename"],
                "file_type": document["file_type"],
                "word_count": document["word_count"],
                "char_count": document["char_count"],
                "processed_at": document["processed_at"]
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_documents', methods=['GET'])
def get_documents():
    """Endpoint per ottenere tutti i documenti trascritti"""
    try:
        documents = processor.get_all_documents()
        return jsonify({
            "success": True,
            "documents": [{
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "word_count": doc["word_count"],
                "char_count": doc["char_count"],
                "processed_at": doc["processed_at"]
            } for doc in documents],
            "session_id": processor.transcripts["session_id"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_document_text/<doc_id>', methods=['GET'])
def get_document_text(doc_id):
    """Endpoint per ottenere il testo di un documento specifico"""
    try:
        documents = processor.get_all_documents()
        document = next((doc for doc in documents if doc["id"] == doc_id), None)
        
        if not document:
            return jsonify({"error": "Documento non trovato"}), 404
        
        return jsonify({
            "success": True,
            "document": document
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/remove_document/<doc_id>', methods=['DELETE'])
def remove_document(doc_id):
    """Endpoint per rimuovere un documento"""
    try:
        processor.remove_document(doc_id)
        return jsonify({"success": True, "message": "Documento rimosso"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Endpoint per pulire la sessione"""
    try:
        processor.clear_session()
        return jsonify({"success": True, "message": "Sessione pulita"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_company_info/<doc_id>', methods=['GET'])
def get_company_info(doc_id):
    """Endpoint per ottenere le informazioni aziendali di un documento specifico"""
    try:
        documents = processor.get_all_documents()
        document = next((doc for doc in documents if doc["id"] == doc_id), None)
        
        if not document:
            return jsonify({"error": "Documento non trovato"}), 404
        
        company_info = document.get("company_info", {})
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "filename": document["filename"],
            "company_info": company_info,
            "extracted_fields_count": len([v for v in company_info.values() if v])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_company_info', methods=['GET'])
def get_all_company_info():
    """Endpoint per ottenere le informazioni aziendali di tutti i documenti"""
    try:
        documents = processor.get_all_documents()
        company_data = []
        
        for doc in documents:
            company_info = doc.get("company_info", {})
            if company_info:  # Solo se ci sono informazioni estratte
                company_data.append({
                    "document_id": doc["id"],
                    "filename": doc["filename"],
                    "processed_at": doc["processed_at"],
                    "company_info": company_info,
                    "extracted_fields_count": len([v for v in company_info.values() if v])
                })
        
        return jsonify({
            "success": True,
            "total_documents": len(documents),
            "documents_with_company_info": len(company_data),
            "company_data": company_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_info_base', methods=['GET'])
def get_info_base():
    """Endpoint per ottenere InfoBase con tutte le informazioni aziendali estratte"""
    try:
        return jsonify({
            "success": True,
            "InfoBase": processor.transcripts.get("InfoBase", {})
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/extract_company_info/<doc_id>', methods=['POST'])
def extract_company_info_from_existing(doc_id):
    """Endpoint per ri-estrarre le informazioni aziendali da un documento esistente"""
    try:
        documents = processor.get_all_documents()
        doc_index = next((i for i, doc in enumerate(documents) if doc["id"] == doc_id), None)
        
        if doc_index is None:
            return jsonify({"error": "Documento non trovato"}), 404
        
        document = documents[doc_index]
        text = document["text"]
        
        # Ri-estrae le informazioni aziendali
        company_info = processor.company_extractor.extract_company_info(text)
        
        # Aggiorna il documento
        processor.transcripts["documents"][doc_index]["company_info"] = company_info
        processor.save_transcripts()
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "filename": document["filename"],
            "company_info": company_info,
            "extracted_fields_count": len([v for v in company_info.values() if v])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint per verificare lo stato del server"""
    return jsonify({"status": "ok", "message": "Document processor server is running"})

# Cleanup automatico alla chiusura
import atexit

def cleanup_on_exit():
    """Pulisce tutti i documenti alla chiusura del server"""
    processor = DocumentProcessor()
    processor.clear_session()
    print("\n🧹 Documenti puliti alla chiusura del server")

atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    print("🚀 Server di trascrizione documenti avviato su http://localhost:5000")
    print("📄 Formati supportati: PDF, DOCX, TXT")
    print("🏢 Estrazione automatica informazioni aziendali (P.IVA, CF, Ragione Sociale, etc.)")
    print("🔄 I documenti verranno automaticamente puliti alla chiusura")
    print("\n📋 Endpoint disponibili:")
    print("   POST /process_document - Carica e processa documento")
    print("   GET  /get_documents - Lista tutti i documenti")
    print("   GET  /get_info_base - InfoBase con tutte le aziende estratte")
    print("   GET  /get_company_info/<doc_id> - Info aziendali documento specifico")
    print("   GET  /get_all_company_info - Info aziendali tutti i documenti")
    print("   POST /extract_company_info/<doc_id> - Ri-estrae info aziendali")
    app.run(host='0.0.0.0', port=5000, debug=True)