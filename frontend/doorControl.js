function toggleSwitch(type) {
    const toggle = document.getElementById(type + '-toggle');
    toggle.classList.toggle('active');
    
    if (type === 'auto') {
        console.log('Chế độ tự động:', toggle.classList.contains('active') ? 'Bật' : 'Tắt');
    } else {
        console.log('Mở cửa thủ công:', toggle.classList.contains('active') ? 'Mở' : 'Đóng');
    }
}

async function sendOpenDoor() {
    const statusEl = document.getElementById('open-door-status');
    statusEl.textContent = 'Đang gửi lệnh...';

    try {
        // Build a sensible backend URL: prefer same origin, otherwise fall back to localhost:8000
        let backendBase = window.location.origin;
        if (!backendBase || backendBase === 'null' || backendBase === 'file://') {
            backendBase = 'http://localhost:8000';
        }
        const url = backendBase + '/open-door';
        console.log('[sendOpenDoor] POST', url);
        const resp = await fetch(url, { method: 'POST' });
        if (!resp.ok) {
            const txt = await resp.text();
            console.error('[sendOpenDoor] error response', resp.status, txt);
            statusEl.textContent = 'Lỗi: ' + txt;
            return;
        }
        const data = await resp.json();
        console.log('[sendOpenDoor] success', data);
        statusEl.textContent = data.message || 'Lệnh mở cửa đã gửi';
    } catch (err) {
        console.error('[sendOpenDoor] exception', err);
        statusEl.textContent = 'Lỗi kết nối: ' + err.message; 
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('open-door-btn');
    if (btn) btn.addEventListener('click', sendOpenDoor);
});