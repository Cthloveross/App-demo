async function fetchSensorData(sensorType) {
    try {
        const response = await fetch(`/api/${sensorType}`);
        const data = await response.json();

        return data.map(entry => ({
            timestamp: new Date(entry.timestamp),
            value: parseFloat(entry.value)
        }));
    } catch (error) {
        console.error(`Error fetching ${sensorType} data:`, error);
        return [];
    }
}
async function createChart(sensorType, canvasId, label, unit) {
    console.log(`Creating chart for ${sensorType}...`);
    const sensorData = await fetchSensorData(sensorType);
    
    if (sensorData.length === 0) {
        console.warn(`No data found for ${sensorType}`);
        return;
    }

    const ctx = document.getElementById(canvasId).getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: sensorData.map(entry => entry.timestamp.toLocaleString()),
            datasets: [{
                label: `${label} (${unit})`,
                data: sensorData.map(entry => entry.value),
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                pointRadius: 4,
                tension: 0.4
            }]
        },
        options: {
            responsive: false,  // ❌ Prevent Chart.js from auto-resizing
            maintainAspectRatio: false,  // ❌ Allow manual size control
            scales: {
                x: { title: { display: true, text: 'Timestamp' }},
                y: { title: { display: true, text: `Value (${unit})` }}
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    createChart('temperature', 'temperatureChart', 'Temperature', '°C');
    createChart('humidity', 'humidityChart', 'Humidity', '%');
    createChart('light', 'lightChart', 'Light Intensity', 'lux');
});
