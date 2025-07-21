"""
Módulo manejador de email para monitoreo y procesamiento de emails.

Este módulo maneja:
- Conexión al servidor IMAP (Strato)
- Verificación de emails con palabras clave específicas y adjuntos
- Descarga y validación de adjuntos
- Extracción de archivos para procesamiento
"""

import imaplib
import email
from email.message import EmailMessage
import os
import tempfile
from typing import List, Optional, Tuple
import logging

from config import config


class EmailHandler:
    """Maneja el monitoreo de emails y procesamiento de adjuntos."""
    
    def __init__(self):
        """Inicializa el manejador de email con configuración."""
        self.imap_host = config.imap_host
        self.imap_port = config.imap_port
        self.username = config.imap_username
        self.password = config.imap_password
        self.monitored_email = config.monitored_email
        self.keywords = config.email_keywords
        self.allowed_extensions = config.allowed_extensions
        self.max_file_size = config.max_file_size_mb * 1024 * 1024  # Convertir a bytes
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def connect_to_imap(self) -> imaplib.IMAP4_SSL:
        """Conecta al servidor IMAP y se autentica."""
        try:
            # Conectar al servidor IMAP
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)
            
            self.logger.info(f"Conectado exitosamente al servidor IMAP: {self.imap_host}")
            return mail
            
        except Exception as e:
            self.logger.error(f"Falló la conexión al servidor IMAP: {e}")
            raise
    
    def check_for_new_emails(self) -> List[Tuple[str, str]]:
        """
        Verifica nuevos emails con palabras clave y adjuntos.
        
        Returns:
            Lista de tuplas que contienen (email_id, attachment_filename)
        """
        mail = None
        found_files = []
        
        try:
            mail = self.connect_to_imap()
            mail.select('INBOX')
            
            # Buscar emails no leídos a la dirección monitoreada
            search_criteria = f'(UNSEEN TO "{self.monitored_email}")'
            status, message_ids = mail.search(None, search_criteria)
            
            if status != 'OK' or not message_ids[0]:
                self.logger.info("No se encontraron nuevos emails")
                return found_files
            
            # Procesar cada email
            for email_id in message_ids[0].split():
                email_id_str = email_id.decode()
                
                # Obtener el email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # Analizar el email
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Verificar si el email tiene palabras clave relevantes y adjuntos
                if self._has_relevant_content(email_message):
                    attachment_files = self._process_attachments(email_message)
                    for filename in attachment_files:
                        found_files.append((email_id_str, filename))
                        
                        # Marcar email como leído después del procesamiento
                        mail.store(email_id, '+FLAGS', '\\Seen')
            
            self.logger.info(f"Se encontraron {len(found_files)} archivos relevantes en emails")
            return found_files
            
        except Exception as e:
            self.logger.error(f"Error verificando emails: {e}")
            return found_files
            
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
    
    def _has_relevant_content(self, email_message: EmailMessage) -> bool:
        """
        Verifica si el email tiene palabras clave relevantes en asunto o cuerpo.
        
        Args:
            email_message: El mensaje de email a verificar
            
        Returns:
            True si el email contiene palabras clave relevantes
        """
        # Obtener asunto y texto del cuerpo
        subject = email_message.get('Subject', '').lower()
        
        # Obtener cuerpo del email
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
        
        # Verificar si alguna palabra clave está presente
        content = f"{subject} {body}"
        has_keywords = any(keyword in content for keyword in self.keywords)
        
        if has_keywords:
            self.logger.info(f"El email contiene palabras clave relevantes: {subject}")
        
        return has_keywords
    
    def _process_attachments(self, email_message: EmailMessage) -> List[str]:
        """
        Procesa y guarda adjuntos válidos del email.
        
        Args:
            email_message: El mensaje de email a procesar
            
        Returns:
            Lista de nombres de archivos adjuntos guardados
        """
        saved_files = []
        
        # Procesar adjuntos
        for part in email_message.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                
                if not filename:
                    continue
                
                # Verificar si el archivo tiene una extensión válida
                file_extension = filename.lower().split('.')[-1]
                if file_extension not in self.allowed_extensions:
                    self.logger.info(f"Omitiendo archivo con extensión inválida: {filename}")
                    continue
                
                # Obtener contenido del archivo
                file_content = part.get_payload(decode=True)
                
                # Verificar tamaño del archivo
                if len(file_content) > self.max_file_size:
                    self.logger.warning(f"Archivo demasiado grande, omitiendo: {filename}")
                    continue
                
                # Guardar archivo en directorio temporal
                try:
                    temp_dir = tempfile.gettempdir()
                    file_path = os.path.join(temp_dir, f"email_{filename}")
                    
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    saved_files.append(file_path)
                    self.logger.info(f"Adjunto guardado: {file_path}")
                    
                except Exception as e:
                    self.logger.error(f"Error guardando adjunto {filename}: {e}")
        
        return saved_files
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """
        Limpia archivos temporales.
        
        Args:
            file_paths: Lista de rutas de archivos a eliminar
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.info(f"Archivo temporal limpiado: {file_path}")
            except Exception as e:
                self.logger.warning(f"No se pudo eliminar archivo temporal {file_path}: {e}")


def check_email_trigger() -> List[str]:
    """
    Función principal para verificar triggers de email.
    
    Returns:
        Lista de rutas de archivos a procesar
    """
    handler = EmailHandler()
    
    try:
        # Verificar nuevos emails
        email_files = handler.check_for_new_emails()
        
        # Extraer solo las rutas de archivos
        file_paths = [filename for _, filename in email_files]
        
        return file_paths
        
    except Exception as e:
        logging.error(f"Error en verificación de trigger de email: {e}")
        return [] 