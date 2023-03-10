from flask import Blueprint, request, jsonify
from services.fft_service import fft_mrc

fft_view = Blueprint('fft_view', __name__)


@fft_view.route('/fft', methods=['POST'])
def fft():
    file = request.files['file']
    filename = file.filename
    file.save(filename)
    fft_data = fft_mrc(filename)
    return jsonify({'fft': fft_data.tolist()})
