if (!window.location.pathname.endsWith('/')) {
    window.location.pathname += '/';
}

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

function uploadFile(path, file) {
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

        xhr.upload.onprogress = function (event) {
            if (event.lengthComputable) {
                var percentComplete = event.loaded / event.total;
                var progress = document.getElementById("uploadProgress");
                progress.value = percentComplete * 100;
                progress.style.display = "block";
            }
        }

        xhr.onerror = function () {
            console.error('Upload failed.');
            progress.style.display = "none";
            alert(xhr.status + ' ' + xhr.statusText)
        };

        xhr.send(formData);
    }
}

function fileElementMenuContextMenuListenerGenerator(items) {
    return function(e) {
        var rcMenu = document.querySelector(".rc_menu");
        rcMenu.innerHTML = "";
        items.forEach(function(item) {
            var li = document.createElement("li");
            li.textContent = item[0];
            li.addEventListener("click", item[1]);
            rcMenu.appendChild(li);
        });
        
        e.preventDefault();
        let windowWidth = window.innerWidth;
        let windowHeight = window.innerHeight;
        let cursorX = e.pageX;
        let cursorY = e.pageY;
        let menuWidth = rcMenu.getBoundingClientRect().width;
        let menuHeight = rcMenu.getBoundingClientRect().height;
        let menuX = cursorX + menuWidth > windowWidth ? windowWidth - menuWidth : cursorX;
        let menuY = cursorY + menuHeight > windowHeight ? windowHeight - menuHeight : cursorY;
        rcMenu.style.left = menuX + "px";
        rcMenu.style.top = menuY + "px";
        rcMenu.style.display = "block";
    }
}

function setBreadcrumb(path) {
    var breadcrumb = document.querySelector(".bread_crumb .path_elements");
    breadcrumb.innerHTML = "";

    path.forEach(function(folder_name, index) {
        if (index === path.length - 1) return;
        var li = document.createElement("li");
        li.textContent = folder_name;
        breadcrumb.appendChild(li);
    });
}

function displayFolderContentsAsIcons(list) {
    var fileList = document.querySelector(".file_list");
    fileList.innerHTML = "";

    list.forEach(function(item) {
        var icon_panel = document.createElement("div");
        icon_panel.className = "file_icon_panel";

        // icon
        var icon = document.createElement("i");
        icon.className = item.charAt(item.length - 1) === "/" ? "iconfont icon-folder" : "iconfont icon-file";
        icon_panel.appendChild(icon);

        // text
        var text = document.createElement("p");
        text.title = item.charAt(item.length - 1) === "/" ? item.substr(0, item.length - 1) : item;
        text.textContent = item.charAt(item.length - 1) === "/" ? item.substr(0, item.length - 1) : item;
        icon_panel.appendChild(text);

        // events
        icon_panel.addEventListener("click", function() {
            window.location.href = "./" + item;
        });
        icon_panel.addEventListener("contextmenu", fileElementMenuContextMenuListenerGenerator([
            ["Open", function() {
                window.location.href = "./" + item;
            }],
            ["Rename", function() {
                var new_name = prompt("Please enter the new name", item);
                if (new_name != null) {
                    // TODO: validate new_name
                    var xhr = new XMLHttpRequest();
                    xhr.open('POST', '{{ file_manager_api_route }}/rename?path=' + window.location.pathname + item + '&rename=' + new_name, true);

                    xhr.onload = function () {
                        window.location.reload();
                        console.log('Rename successfully.');
                        alert(xhr.status + ' ' + xhr.statusText)
                    };

                    xhr.onerror = function () {
                        console.error('Rename failed.');
                        alert(xhr.status + ' ' + xhr.statusText)
                    };

                    xhr.send('');
                }
            }],
            ["Delete", function() {
                deleteFile(window.location.pathname + item);
            }]
        ]));
        
        fileList.appendChild(icon_panel);
    });

    // upload icon
    var icon_panel = document.createElement("div");
    icon_panel.className = "upload_icon_panel";

    var icon = document.createElement("i");
    icon.className = "iconfont icon-plus";
    icon_panel.appendChild(icon);

    var progress = document.createElement("progress");
    progress.id = "uploadProgress";
    progress.value = 0;
    progress.max = 100;
    icon_panel.appendChild(progress);

    icon_panel.addEventListener("click", function() {
        var uploadButton = document.getElementById("uploadButton");
        uploadButton.click();
    });

    fileList.appendChild(icon_panel);
}

function displayFolderContentsAsList(contents) { // Deserted
    var fileDisplay = document.querySelector(".file_list");
    fileDisplay.innerHTML = "";
    
    var ul = document.createElement("ul");
    ul.className = "icon-list";

    contents.forEach(function(item) {
        var li = document.createElement("li");
        var icon = document.createElement("i");
        icon.className = item.charAt(item.length - 1) === "/" ? "iconfont icon-folder folder-icon" : "iconfont icon-file file-icon";
        var h5 = document.createElement("h5");
        h5.textContent = item.charAt(item.length - 1) === "/" ? item.substr(0, item.length - 1) : item;

        icon.style.fontSize = "16px";

        icon.addEventListener("click", function() {
            window.location.href = "./" + item;
        });

        li.style.display = "flex";
        var icon2 = document.createElement("i");
        icon2.className = "iconfont icon-shanchu";
        icon2.style.fontSize = "16px";
        
        icon2.addEventListener("click", function() {
            deleteFile(window.location.pathname + item);
        });
        li.appendChild(icon);
        li.appendChild(h5);
        ul.appendChild(li);
        li.appendChild(icon2);
    });

    fileDisplay.appendChild(ul);
}

function initialize() {
    // resort the list
    list.sort(function(a, b) {
        if (a.endsWith('/') && !b.endsWith('/')) {
            return -1;
        } else if (!a.endsWith('/') && b.endsWith('/')) {
            return 1;
        } else {
            return a.localeCompare(b);
        }
    })

    // breadcrumb
    setBreadcrumb(path.split('/'))

    // view mode
    var isListView = false;
    displayFolderContentsAsIcons(list);

    // upload button
    var uploadButton = document.getElementById("uploadButton");
    uploadButton.addEventListener("click", function() {
        var fileInput = document.getElementById("fileInput");
        fileInput.click();
    });
    var uploadForm = document.getElementById("uploadForm");
    uploadForm.addEventListener("change", function() {
        var fileInput = document.getElementById("fileInput");
        var file = fileInput.files[0];
        uploadFile(window.location.pathname, file);
    });

    // new folder button
    var newFolderButton = document.getElementById("newFolderButton");
    newFolderButton.addEventListener("click", function() {
        var folder_name = prompt("Please enter the folder name", "New Folder");
        if (folder_name != null) {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '{{ file_manager_api_route }}/new_folder?path=' + window.location.pathname + folder_name, true);

            xhr.onload = function () {
                window.location.reload();
                console.log('Create successfully.');
                alert(xhr.status + ' ' + xhr.statusText)
            };

            xhr.onerror = function () {
                console.error('Create failed.');
                alert(xhr.status + ' ' + xhr.statusText)
            };

            xhr.send('');
        }
    });
    
    // back button
    var backButton = document.getElementById("backButton");
    backButton.addEventListener("click", function() {
        window.location.href = "../";
    });

    // toggle view button
    var toggleViewButton = document.getElementById("toggleViewButton");
    toggleViewButton.addEventListener("click", function() {
        isListView = !isListView;
        if (isListView) {
            displayFolderContentsAsList(list);
        } else {
            displayFolderContentsAsIcons(list);
        }
    });

    // file element menu
    document.addEventListener("click", function() {
        var rcMenu = document.querySelector(".rc_menu");
        rcMenu.style.display = "none";
    });
}
