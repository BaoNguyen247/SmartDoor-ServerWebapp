function toggleSwitch(type) {
    const toggle = document.getElementById(type + '-toggle');
    if (!toggle) {
        console.error(`[toggleSwitch] Toggle element not found: ${type}-toggle`);
        return;
    }
    toggle.classList.toggle('active');
    
    if (type === 'auto') {
        console.log('Chế độ tự động:', toggle.classList.contains('active') ? 'Bật' : 'Tắt');
    } else {
        console.log('Mở cửa thủ công:', toggle.classList.contains('active') ? 'Mở' : 'Đóng');
    }
}

async function sendOpenDoor() {
    const statusEl = document.getElementById('open-door-status');
    if (!statusEl) {
        console.error('[sendOpenDoor] Status element not found: open-door-status');
        alert('Lỗi: Không tìm thấy phần tử trạng thái');
        return;
    }
    
    statusEl.textContent = 'Đang gửi lệnh...';
    statusEl.className = 'mt-3 text-sm text-gray-600';

    try {
        // Always use localhost:8000 for backend API
        const url = 'http://localhost:8000/open-door';
        console.log('[sendOpenDoor] POST', url);
        
        const resp = await fetch(url, { method: 'POST' });
        
        if (!resp.ok) {
            const txt = await resp.text();
            console.error('[sendOpenDoor] error response', resp.status, txt);
            statusEl.textContent = `❌ Lỗi ${resp.status}`;
            statusEl.className = 'mt-3 text-sm text-red-600';
            return;
        }
        
        const data = await resp.json();
        console.log('[sendOpenDoor] success', data);
        statusEl.textContent = '✓ ' + (data.message || 'Lệnh mở cửa đã gửi');
        statusEl.className = 'mt-3 text-sm text-green-600';
        
        setTimeout(() => {
            statusEl.textContent = '';
        }, 3000);
    } catch (err) {
        console.error('[sendOpenDoor] exception', err);
        statusEl.textContent = '❌ Lỗi kết nối: ' + err.message;
        statusEl.className = 'mt-3 text-sm text-red-600';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('[doorControl.js] DOMContentLoaded fired');
    
    const btn = document.getElementById('open-door-btn');
    if (!btn) {
        console.error('[doorControl.js] Button not found: open-door-btn');
        return;
    }
    
    console.log('[doorControl.js] Button found, attaching click handler');
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        sendOpenDoor();
    });
});