'use strict';

define(function(require){

	var $ = require('jquery');
	var d3 = require('d3');

	class Chart{
		constructor(element){
			console.log('connecting the chart');

			this.svg = d3.select(element);
		}


	}


	return Chart;
});