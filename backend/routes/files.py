"""
Attachments API.

POST   /api/files          multipart "file"  -> {id, name, kind, size, info, note, chars}
GET    /api/files/<id>     metadata + the first part of the extracted text
DELETE /api/files/<id>
"""

from flask import Blueprint, request, jsonify

from models import UploadDocument
from orchestrator import files
from auth import current_user

files_bp = Blueprint('files', __name__)


def _mine(fid):
    u = UploadDocument.objects(upload_id=fid).first()
    return u if u and u.owner == current_user()['u'] else None


@files_bp.route('/files', methods=['POST'])
def upload():
    f = request.files.get('file')
    if f is None:
        return jsonify({'error': 'send the file as multipart field "file"'}), 400
    data = f.read(files.MAX_BYTES + 1)
    try:
        u = files.save_upload(current_user()['u'], f.filename or 'file', data)
    except files.FileError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(u.to_dict()), 201


@files_bp.route('/files/<fid>', methods=['GET'])
def get_file(fid):
    u = _mine(fid)
    if not u:
        return jsonify({'error': 'not found'}), 404
    return jsonify({**u.to_dict(), 'text': u.text[:3000]})


@files_bp.route('/files/<fid>', methods=['DELETE'])
def delete_file(fid):
    u = _mine(fid)
    if not u:
        return jsonify({'error': 'not found'}), 404
    files.delete_upload(u)
    return jsonify({'ok': True})
