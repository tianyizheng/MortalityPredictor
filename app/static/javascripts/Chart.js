'use strict';

define(function(require){

	var $ = require('jquery');
	var d3 = require('d3');


	class Chart{
		constructor(parent){
			console.log('making a chart 4');

			this.svg = d3.select(parent).append('svg')
				.attr('class', 'chart')
				.attr('width', 500)
				.attr('height', 500);



		}


	}


	return Chart;
});