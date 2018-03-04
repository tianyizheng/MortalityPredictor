'use strict';

define(function(require){

	console.log('hello 5');

	var $ = require('jquery');
	//var bootstrap = require('bootstrap');
	var Chart = require('Chart');


	class Page{
		constructor(){

			var element = $('#content');

			var chart = new Chart(element[0]);

		}

	}

	$(document).ready(function() { 
		console.log('Page ready');

		var page = new Page();
	});

	return {};
});