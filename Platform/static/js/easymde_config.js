function initializeEasyMDE(config) {
    const { elementId, initialValue, csrfToken, uploadUrl } = config;

    const easyMDE = new EasyMDE({
        element: document.getElementById(elementId),
        spellChecker: false,
        initialValue: initialValue || '',
        uploadImage: true,
        imageMaxSize: 2 * 1024 * 1024, // 2MB
        imageAccept: "image/jpeg, image/png, image/gif, image/webp, image/tiff, image/bmp, image/svg+xml",
        sideBySideFullscreen: false,
        imageUploadFunction: (file, onSuccess, onError) => {
            const formData = new FormData();
            formData.append("image", file);

            fetch(uploadUrl, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken,
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.url) {
                    onSuccess(data.url);
                } else {
                    onError(data.error || "Image upload failed.");
                }
            })
            .catch(error => {
                console.error("Image upload error:", error);
                onError("Image upload failed. See console for details.");
            });
        },
        errorCallback: (errorMessage) => {
            alert(`An error occurred: ${errorMessage}`);
        },
    });

    easyMDE.toggleSideBySide();

    return easyMDE;
}
