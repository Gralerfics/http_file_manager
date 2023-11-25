var pathInput = document.getElementById('pathInput');
var directoryList = document.getElementById('directoryList');

if (!window.location.pathname.endsWith('/')) {
    window.location.pathname += '/';
}

['..', '.'].concat(list).forEach(function(item) {
    var linkItem = document.createElement('a');
    linkItem.textContent = item;
    if (item === '..') {
        linkItem.href = '../';
    } else if (item === '.') {
        linkItem.href = './';
    } else {
        linkItem.href = './' + item;
    }
    var listItem = document.createElement('li');
    listItem.appendChild(linkItem);
    directoryList.appendChild(listItem);
});
