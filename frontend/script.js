// ================================
// CONFIGURACIÓN Y VARIABLES GLOBALES
// ================================

const API_BASE_URL = 'http://localhost:8000';
let currentJobId = null;
let pollingInterval = null;
let itemCounter = 1; // Contador para IDs únicos de items

// Referencias a elementos DOM
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const statusIndicator = document.getElementById('statusIndicator');
const loadingSpinner = document.getElementById('loadingSpinner');
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const form = document.getElementById('facturaForm');
const itemsTableBody = document.getElementById('itemsTableBody');

// Referencias para cálculos automáticos
const subtotalInput = document.getElementById('subtotal');
const igvInput = document.getElementById('igv');
const totalInput = document.getElementById('total');
const porcentajeDetraccionInput = document.getElementById('porcentaje_detraccion');
const montoDetraccionInput = document.getElementById('monto_detraccion');

// ================================
// CONFIGURACIÓN DE EVENTOS
// ================================

// Eventos de drag & drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
        handleFileSelection(files[0]);
    } else {
        showStatus('error', 'Por favor selecciona un archivo PDF válido');
    }
});

// Evento de click en área de upload
uploadArea.addEventListener('click', () => {
    fileInput.click();
});

// Evento de selección de archivo
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
    }
});

// Evento de envío del formulario
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = collectFormData();
    
    try {
        showStatus('processing', 'Generando archivo Excel...');
        
        const response = await fetch(`${API_BASE_URL}/guardar-factura-excel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            // Obtener el archivo Excel como blob
            const blob = await response.blob();
            
            // Extraer nombre del archivo desde los headers (si está disponible)
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'factura.xlsx';
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            // Crear URL temporal y descargar
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            
            // Limpiar
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showStatus('success', `✅ Excel descargado: ${filename}`);
            
            // Opcional: Limpiar formulario después de 3 segundos
            // setTimeout(() => clearForm(), 3000);
        } else {
            const errorData = await response.json();
            const errorMsg = errorData.detail || 'Error desconocido al generar Excel';
            showStatus('error', `Error: ${errorMsg}`);
        }
        
    } catch (error) {
        console.error('Error generando Excel:', error);
        showStatus('error', `Error de conexión: ${error.message}`);
    }
});

// Eventos para cálculo automático de detracción
porcentajeDetraccionInput.addEventListener('input', calculateDetraccion);

// ================================
// FUNCIONES DE MANEJO DE ITEMS
// ================================

function addItemRow() {
    const newRow = document.createElement('tr');
    newRow.className = 'item-row';
    newRow.dataset.index = itemCounter;
    
    newRow.innerHTML = `
        <td>
            <input type="text" name="item_descripcion_${itemCounter}" placeholder="Ej: SERVICIO DE CONSULTORIA" class="table-input">
        </td>
        <td>
            <input type="number" name="item_cantidad_${itemCounter}" placeholder="1" step="1" min="1" class="table-input" onchange="calculateItemSubtotal(${itemCounter})">
        </td>
        <td>
            <input type="number" name="item_precio_${itemCounter}" placeholder="1500.00" step="0.01" class="table-input" onchange="calculateItemSubtotal(${itemCounter})">
        </td>
        <td>
            <input type="number" name="item_subtotal_${itemCounter}" placeholder="0.00" step="0.01" class="table-input" readonly>
        </td>
        <td>
            <button type="button" class="btn-delete" onclick="removeItemRow(${itemCounter})" title="Eliminar">×</button>
        </td>
    `;
    
    itemsTableBody.appendChild(newRow);
    itemCounter++;
}

function removeItemRow(index) {
    const row = document.querySelector(`.item-row[data-index="${index}"]`);
    if (row) {
        // Solo permitir eliminar si hay más de una fila
        const totalRows = document.querySelectorAll('.item-row').length;
        if (totalRows > 1) {
            row.remove();
            calculateTotals(); // Recalcular totales después de eliminar
        } else {
            showStatus('warning', '⚠️ Debe haber al menos un item en la factura');
        }
    }
}

function calculateItemSubtotal(index) {
    const cantidadInput = document.querySelector(`input[name="item_cantidad_${index}"]`);
    const precioInput = document.querySelector(`input[name="item_precio_${index}"]`);
    const subtotalInput = document.querySelector(`input[name="item_subtotal_${index}"]`);
    
    if (cantidadInput && precioInput && subtotalInput) {
        const cantidad = parseInt(cantidadInput.value) || 0;
        const precio = parseFloat(precioInput.value) || 0;
        const subtotal = cantidad * precio;
        
        subtotalInput.value = subtotal.toFixed(2);
        
        // Animación visual
        subtotalInput.classList.add('auto-calculated');
        setTimeout(() => {
            subtotalInput.classList.remove('auto-calculated');
        }, 1000);
        
        // Recalcular totales generales
        calculateTotals();
    }
}

function calculateTotals() {
    // Sumar todos los subtotales de items
    let totalSubtotal = 0;
    const subtotalInputs = document.querySelectorAll('input[name^="item_subtotal_"]');
    
    subtotalInputs.forEach(input => {
        const value = parseFloat(input.value) || 0;
        totalSubtotal += value;
    });
    
    // Calcular IGV (18%)
    const igv = totalSubtotal * 0.18;
    
    // Calcular total
    const total = totalSubtotal + igv;
    
    // Actualizar campos
    subtotalInput.value = totalSubtotal.toFixed(2);
    igvInput.value = igv.toFixed(2);
    totalInput.value = total.toFixed(2);
    
    // Animación visual
    [subtotalInput, igvInput, totalInput].forEach(input => {
        input.classList.add('auto-calculated');
        setTimeout(() => {
            input.classList.remove('auto-calculated');
        }, 1000);
    });
    
    // Recalcular detracción si hay porcentaje
    calculateDetraccion();
}

function calculateDetraccion() {
    const total = parseFloat(totalInput.value) || 0;
    const porcentaje = parseFloat(porcentajeDetraccionInput.value) || 0;
    
    if (total > 0 && porcentaje > 0) {
        const montoDetraccion = (total * porcentaje) / 100;
        montoDetraccionInput.value = montoDetraccion.toFixed(2);
        
        // Animación visual
        montoDetraccionInput.classList.add('auto-calculated');
        setTimeout(() => {
            montoDetraccionInput.classList.remove('auto-calculated');
        }, 1000);
    } else if (porcentaje === 0) {
        montoDetraccionInput.value = '';
    }
}

// ================================
// FUNCIONES DE RECOLECCIÓN DE DATOS
// ================================

function collectFormData() {
    // Recolectar items
    const items = [];
    const rows = document.querySelectorAll('.item-row');
    
    rows.forEach(row => {
        const index = row.dataset.index;
        const descripcion = document.querySelector(`input[name="item_descripcion_${index}"]`)?.value || '';
        const cantidad = parseInt(document.querySelector(`input[name="item_cantidad_${index}"]`)?.value) || 0;
        const precio = parseFloat(document.querySelector(`input[name="item_precio_${index}"]`)?.value) || 0;
        const subtotal = parseFloat(document.querySelector(`input[name="item_subtotal_${index}"]`)?.value) || 0;
        
        if (descripcion || cantidad > 0) {
            items.push({
                descripcion: descripcion,
                cantidad: cantidad,
                precio_unitario: precio,
                subtotal: subtotal
            });
        }
    });
    
    // Recolectar detracción
    const porcentajeDetraccion = parseFloat(porcentajeDetraccionInput.value) || 0;
    const montoDetraccion = parseFloat(montoDetraccionInput.value) || 0;
    const detraccion = (porcentajeDetraccion > 0 || montoDetraccion > 0) ? {
        porcentaje: porcentajeDetraccion,
        monto: montoDetraccion
    } : null;
    
    // Construir objeto completo
    return {
        codigo_cliente: document.getElementById('codigo').value || null,
        razon_social_cliente: document.getElementById('nombre_empresa').value || null,
        direccion_cliente: document.getElementById('direccion').value || null,
        distrito: document.getElementById('distrito').value || null,
        items: items,
        forma_pago: document.getElementById('forma_pago').value || null,
        moneda: document.getElementById('moneda').value || null,
        subtotal: parseFloat(subtotalInput.value) || null,
        igv: parseFloat(igvInput.value) || null,
        total: parseFloat(totalInput.value) || null,
        detraccion: detraccion
    };
}

// ================================
// FUNCIONES PRINCIPALES DE PROCESAMIENTO
// ================================

async function handleFileSelection(file) {
    if (file.type !== 'application/pdf') {
        showStatus('error', 'Solo se permiten archivos PDF');
        return;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB límite
        showStatus('error', 'El archivo es demasiado grande (máximo 10MB)');
        return;
    }

    // Limpiar cualquier polling anterior
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }

    try {
        // Fase 1: Upload
        showStatus('processing', `Subiendo: ${file.name}`);
        showLoading(true);
        updateProgress(10, 'Subiendo archivo...');

        const uploadResult = await uploadFile(file);
        currentJobId = uploadResult.job_id;

        // Fase 2: Polling para estado
        updateProgress(20, 'Procesamiento iniciado...');
        showStatus('processing', `Procesando: ${file.name}`);
        
        startPolling(currentJobId);

    } catch (error) {
        console.error('Error:', error);
        showStatus('error', `Error: ${error.message}`);
        hideProgress();
        showLoading(false);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Error del servidor: ${response.status} - ${errorText}`);
    }

    return await response.json();
}

function startPolling(jobId) {
    let attempts = 0;
    const maxAttempts = 60; // 2 minutos máximo (60 * 2 segundos)

    pollingInterval = setInterval(async () => {
        attempts++;
        
        try {
            const status = await checkJobStatus(jobId);
            
            switch (status.status) {
                case 'PENDING':
                    updateProgress(30, 'En cola de procesamiento...');
                    break;
                    
                case 'PROCESSING':
                    updateProgress(60, 'Extrayendo datos...');
                    break;
                    
                case 'COMPLETED':
                    clearInterval(pollingInterval);
                    await handleJobCompletion(jobId);
                    break;
                    
                case 'FAILED':
                    clearInterval(pollingInterval);
                    handleJobFailure(status.error);
                    break;
            }
            
            // Timeout después de máximos intentos
            if (attempts >= maxAttempts) {
                clearInterval(pollingInterval);
                showStatus('error', 'Timeout: El procesamiento está tomando demasiado tiempo');
                hideProgress();
                showLoading(false);
            }
            
        } catch (error) {
            console.error('Error en polling:', error);
            
            // Si hay muchos errores consecutivos, detener
            if (attempts >= 5) {
                clearInterval(pollingInterval);
                showStatus('error', 'Error de conexión durante el procesamiento');
                hideProgress();
                showLoading(false);
            }
        }
    }, 2000); // Polling cada 2 segundos
}

async function checkJobStatus(jobId) {
    const response = await fetch(`${API_BASE_URL}/status/${jobId}`);
    
    if (!response.ok) {
        throw new Error(`Error al consultar estado: ${response.status}`);
    }
    
    return await response.json();
}

async function handleJobCompletion(jobId) {
    try {
        updateProgress(90, 'Obteniendo resultados...');
        
        const result = await getJobResult(jobId);
        
        updateProgress(100, '¡Completado!');
        
        if (result.extracted_data) {
            fillFormWithExtractedData(result.extracted_data);
            showStatus('success', 'Datos extraídos automáticamente');
        } else {
            showStatus('error', 'No se pudieron extraer datos del archivo');
        }
        
        // Ocultar progreso después de un momento
        setTimeout(() => {
            hideProgress();
        }, 2000);
        
    } catch (error) {
        console.error('Error al obtener resultado:', error);
        showStatus('error', `Error al obtener resultado: ${error.message}`);
        hideProgress();
    } finally {
        showLoading(false);
    }
}

async function getJobResult(jobId) {
    const response = await fetch(`${API_BASE_URL}/result/${jobId}`);
    
    if (!response.ok) {
        throw new Error(`Error al obtener resultado: ${response.status}`);
    }
    
    return await response.json();
}

function handleJobFailure(error) {
    showStatus('error', `Error en procesamiento: ${error}`);
    hideProgress();
    showLoading(false);
}

// ================================
// FUNCIONES DE LLENADO DE FORMULARIO
// ================================

function fillFormWithExtractedData(data) {
    console.log('Datos recibidos del backend:', data);
    
    // Limpiar items existentes primero
    clearAllItems();
    
    // Llenar campos simples
    fillField('codigo', data.codigo_cliente);
    fillField('nombre_empresa', data.razon_social_cliente);
    fillField('direccion', data.direccion_cliente);
    fillField('distrito', data.distrito);
    fillField('forma_pago', data.forma_pago);
    fillField('moneda', data.moneda);
    
    // Llenar items (array)
    if (data.items && Array.isArray(data.items) && data.items.length > 0) {
        data.items.forEach((item, index) => {
            if (index === 0) {
                // Usar la primera fila existente
                fillItemRow(0, item);
            } else {
                // Crear nuevas filas para items adicionales
                addItemRow();
                fillItemRow(itemCounter - 1, item);
            }
        });
        
        // Mostrar advertencia si hay muchos items
        if (data.items.length > 1) {
            showStatus('success', `${data.items.length} items extraídos correctamente`);
        }
    }
    
    // Llenar totales (estos se calculan automáticamente, pero los llenamos por si acaso)
    fillField('subtotal', data.subtotal);
    fillField('igv', data.igv);
    fillField('total', data.total);
    
    // Llenar detracción (objeto)
    if (data.detraccion) {
        fillField('porcentaje_detraccion', data.detraccion.porcentaje);
        fillField('monto_detraccion', data.detraccion.monto);
    } else {
        fillField('porcentaje_detraccion', 0);
        fillField('monto_detraccion', 0);
    }
    
    // Scroll suave hacia el formulario
    document.querySelector('.form-section').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

function fillItemRow(index, itemData) {
    const descripcionInput = document.querySelector(`input[name="item_descripcion_${index}"]`);
    const cantidadInput = document.querySelector(`input[name="item_cantidad_${index}"]`);
    const precioInput = document.querySelector(`input[name="item_precio_${index}"]`);
    const subtotalInput = document.querySelector(`input[name="item_subtotal_${index}"]`);
    
    if (descripcionInput && itemData.descripcion) {
        descripcionInput.value = itemData.descripcion;
        descripcionInput.classList.add('auto-filled');
        setTimeout(() => descripcionInput.classList.remove('auto-filled'), 3000);
    }
    
    if (cantidadInput && itemData.cantidad) {
        cantidadInput.value = itemData.cantidad;
        cantidadInput.classList.add('auto-filled');
        setTimeout(() => cantidadInput.classList.remove('auto-filled'), 3000);
    }
    
    if (precioInput && itemData.precio_unitario) {
        precioInput.value = itemData.precio_unitario.toFixed(2);
        precioInput.classList.add('auto-filled');
        setTimeout(() => precioInput.classList.remove('auto-filled'), 3000);
    }
    
    if (subtotalInput && itemData.subtotal) {
        subtotalInput.value = itemData.subtotal.toFixed(2);
        subtotalInput.classList.add('auto-filled');
        setTimeout(() => subtotalInput.classList.remove('auto-filled'), 3000);
    }
}

function fillField(fieldId, value) {
    const input = document.getElementById(fieldId);
    if (input && value !== null && value !== undefined) {
        input.value = value;
        input.classList.add('auto-filled');
        setTimeout(() => input.classList.remove('auto-filled'), 3000);
    }
}

function clearAllItems() {
    // Remover todas las filas excepto la primera
    const rows = document.querySelectorAll('.item-row');
    rows.forEach((row, index) => {
        if (index > 0) {
            row.remove();
        }
    });
    
    // Limpiar la primera fila
    const firstRowInputs = document.querySelectorAll('.item-row[data-index="0"] input');
    firstRowInputs.forEach(input => {
        input.value = '';
        input.classList.remove('auto-filled');
    });
    
    // Resetear contador
    itemCounter = 1;
}

// ================================
// FUNCIONES DE INTERFAZ
// ================================

function showStatus(type, message) {
    statusIndicator.className = `status-indicator ${type}`;
    statusIndicator.textContent = message;
    statusIndicator.style.display = 'block';

    if (type === 'success' || type === 'error' || type === 'warning') {
        setTimeout(() => {
            statusIndicator.style.display = 'none';
        }, 5000);
    }
}

function showLoading(show) {
    loadingSpinner.style.display = show ? 'block' : 'none';
}

function updateProgress(percentage, text) {
    progressContainer.style.display = 'block';
    progressFill.style.width = `${percentage}%`;
    progressText.textContent = text;
}

function hideProgress() {
    progressContainer.style.display = 'none';
    progressFill.style.width = '0%';
}

function clearForm() {
    form.reset();
    clearAllItems();
    
    // Limpiar clases de auto-filled
    document.querySelectorAll('.auto-filled').forEach(input => {
        input.classList.remove('auto-filled');
    });
    
    // Resetear totales
    subtotalInput.value = '';
    igvInput.value = '';
    totalInput.value = '';
    
    showStatus('success', '🗑️ Formulario limpiado');
}

// ================================
// INICIALIZACIÓN
// ================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Procesador de Facturas - Demo inicializado');
    console.log('📡 API URL:', API_BASE_URL);
    
    // Asegurarse de que hay al menos una fila de item
    if (!document.querySelector('.item-row')) {
        console.warn('No se encontró ninguna fila de item inicial');
    }
});

// Limpiar polling si se cierra la página
window.addEventListener('beforeunload', () => {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
});