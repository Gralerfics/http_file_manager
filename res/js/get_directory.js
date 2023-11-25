var pathInput = document.getElementById('pathInput');
var directoryList = document.getElementById('directoryList');

["..", "."].concat(list).forEach(function(item) {
    var linkItem = document.createElement('a');

    linkItem.textContent = item;
    linkItem.href = path + '/' + item;

    var listItem = document.createElement('li');
    listItem.appendChild(linkItem);

    directoryList.appendChild(listItem);
});
