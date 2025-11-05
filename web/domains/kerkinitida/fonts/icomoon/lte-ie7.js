(function() {
	function addIcon(el, entity) {
		var html = el.innerHTML;
		el.innerHTML = '<span style="font-family: \'icomoon\'">' + entity + '</span>' + html;
	}
	var icons = {
		'icon-about': '&#xe600;',
		'icon-appartments': '&#xe601;',
		'icon-bar': '&#xe602;',
		'icon-beach': '&#xe603;',
		'icon-contact': '&#xe604;',
		'icon-dolphin': '&#xe605;',
		'icon-evpatory': '&#xe606;',
		'icon-family': '&#xe607;',
		'icon-find': '&#xe608;',
		'icon-home': '&#xe609;',
		'icon-hotel': '&#xe610;',
		'icon-location': '&#xe611;',
		'icon-places': '&#xe612;',
		'icon-quill': '&#xe613;',
		'icon-refresh': '&#xe614;',
		'icon-rest': '&#xe615;',
		'icon-room': '&#xe616;',
		'icon-service': '&#xe617;',
		'icon-transport': '&#xe618;',
		'icon-vilage': '&#xe619;',
		'icon-arrow-left': '&#xe620;',
		'icon-arrow-right': '&#xe621;',
		'0': 0
		},
		els = document.getElementsByTagName('*'),
		i, c, el;
	for (i = 0; ; i += 1) {
		el = els[i];
		if(!el) {
			break;
		}
		c = el.className;
		c = c.match(/icon-[^\s'"]+/);
		if (c && icons[c[0]]) {
			addIcon(el, icons[c[0]]);
		}
	}
}());
