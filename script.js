async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return alert('Выберите файл!');

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const res = await fetch('http://127.0.0.1:8000/upload-archive', { 
            method: 'POST', 
            body: formData 
        });
        const data = await res.json();
        
        document.getElementById('statusArea').classList.remove('hidden');
        
        // Опрос статуса
        const interval = setInterval(async () => {
            const statusRes = await fetch(`http://127.0.0.1:8000/documents/${data.doc_id}/status`);
            const statusData = await statusRes.json();
            
            document.getElementById('statusText').innerText = statusData.status;
            document.getElementById('itemsCount').innerText = statusData.items_extracted;
            
            if (statusData.status === 'done' || statusData.status === 'error') {
                clearInterval(interval);
            }
        }, 2000);
    } catch (e) {
        console.error(e);
        alert('Ошибка сервера');
    }
}