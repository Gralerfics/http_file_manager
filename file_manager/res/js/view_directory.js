var directoryList = document.getElementById('directoryList');

if (!window.location.pathname.endsWith('/')) {
    window.location.pathname += '/';
}

['..', '.'].concat(list).forEach(function(item) {
    var linkItem = document.createElement('a');
    var listItem = document.createElement('li');

    linkItem.textContent = item;
    if (item === '..') {
        linkItem.href = '../';
    } else if (item === '.') {
        linkItem.href = './';
    } else {
        linkItem.href = './' + item;

        var deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = function() {
            deleteFile(window.location.pathname + item);
        };
        deleteButton.style.marginRight = '10px';
        listItem.appendChild(deleteButton);
    }
    listItem.appendChild(linkItem);

    directoryList.appendChild(listItem);
});

function deleteFile(path) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '{{ file_manager_delete_route }}?path=' + path, true);

    xhr.onload = function () {
        window.location.reload();
        console.log('Delete successfully.');
        alert(xhr.status + ' ' + xhr.statusText)
    };

    xhr.onerror = function () {
        console.error('Delete failed.');
        alert(xhr.status + ' ' + xhr.statusText)
    };

    xhr.send('');
}

function uploadFile(path, fileInput) {
    var file = fileInput.files[0];

    if (file) {
        var formData = new FormData();
        formData.append('file', file);

        var xhr = new XMLHttpRequest();
        xhr.open('POST', '{{ file_manager_upload_route }}?path=' + path, true);

        xhr.onload = function () {
            console.log('Upload successfully.');
            alert(xhr.status + ' ' + xhr.statusText)
            window.location.reload();
        };

        xhr.onerror = function () {
            console.error('Upload failed.');
            alert(xhr.status + ' ' + xhr.statusText)
        };

        xhr.send(formData);
    }
}
