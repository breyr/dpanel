function getInfo(containerId) {
    fetch('/info/' + containerId)
        .then(response => response.json())
        .then(data => {
            // Create a new Blob from the JSON string
            var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });

            // Create an object URL from the Blob
            var url = URL.createObjectURL(blob);

            // Open the URL in a new tab
            window.open(url, '_blank');
        });
}