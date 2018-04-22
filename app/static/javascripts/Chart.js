'use strict';

if (!String.prototype.format) {
    String.prototype.format = function() {
        var args = arguments;
        return this.replace(/{(\d+)}/g, function(match, number) { 
            return typeof args[number] != 'undefined'
            ? args[number]
            : match
            ;
        });
    };
}

function calcAngledPoint(sourceX, sourceY, targetX, targetY, angle, scale){

	// find the midpoint
	var midX = (sourceX + targetX) / 2;
	var midY = (sourceY + targetY) / 2; 

	var h = Math.sqrt(Math.pow(midX - sourceX, 2) + Math.pow(midY - sourceY, 2));
	var dx = sourceX - midX;

	var theta = Math.acos(dx / h) + angle;
	var x_ = Math.cos(theta) * (h / scale) + midX;
	var y_ = -Math.sin(theta) * (h / scale) + midY;

	return [x_, y_];
}

class Chart{
	constructor(data, codes, element, infoContainer){
		console.log('connecting the chart 2');
		var self = this;

		this.data = data;
		this.codes = codes;
		this.svg = d3.select(element[0]);
		this.infoContainer = infoContainer;

		this.margin = {top: 20, right: 20, bottom: 30, left: 50};
		this.width = +this.svg.attr('width') - this.margin.left - this.margin.right;
		this.height = +this.svg.attr('height') - this.margin.top - this.margin.bottom;
		this.g = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');
		
		this.x = d3.scaleLinear()
			.rangeRound([0, this.width]);

		this.y = d3.scaleLinear()
			.rangeRound([this.height, 0]);
				
		// x domain needs to be toggleable
		this.x.domain([-1, this.data.length]);
		this.y.domain([0, 1]);
		
		this.line = d3.line()
			.x(function(d, i) { return self.x(self.getX(d, i)); })
			.y(function(d, i) { return self.y(self.getY(d, i)); });
				
		this.svg.append('linearGradient')
			.attr('id', 'temperature-gradient')
			.attr('gradientUnits', 'userSpaceOnUse')
			.attr('x1', 0).attr('y1', this.y(0))
			.attr('x2', 0).attr('y2', this.y(1))
		.selectAll('stop')
			.data([
				{offset: '0%', color: 'steelblue'},
				{offset: '50%', color: 'gray'},
				{offset: '100%', color: 'red'}
			])
		.enter().append('stop')
			.attr('offset', function(d) { return d.offset; })
			.attr('stop-color', function(d) { return d.color; });
		
		this.g.append('g')
			.attr('transform', 'translate(0,' + this.height + ')')
			.attr('class', 'x-axis')

		this.g.append('g')
			.call(d3.axisLeft(this.y))
		.append('text')
			.attr('fill', '#000')
			.attr('transform', 'rotate(-90)')
			.attr('y', 6)
			.attr('dy', '0.71em')
			.attr('text-anchor', 'end')
			.text('Mortality Rate');

		this.g.append('path')
			.datum(this.data)
			.attr('class', 'line')
			.attr('fill', 'none')
			.attr('stroke-linejoin', 'round')
			.attr('stroke-linecap', 'round')
			.attr('stroke-width', 1.5)
			.attr('d', this.line);

		this.g.append('circle')
			.attr('class', 'highlight-circle')
			.attr('fill', 'none')
			.attr('stroke', 'none')
			.attr('stroke-width', 1.5)
			.attr('r', 10)

		this.g.append('circle')
			.attr('class', 'target-circle')
			.attr('fill', 'none')
			.attr('stroke', 'none')
			.attr('stroke-width', 1.5)
			.attr('r', 10)

		this.g.append('circle')
			.attr('class', 'source-circle')
			.attr('fill', 'none')
			.attr('stroke', 'none')
			.attr('stroke-width', 1.5)
			.attr('r', 10);

		this.g.append('path')
			.attr('class', 'contribution-arrow')
			.attr('fill', 'none')
			.attr('stroke-linejoin', 'round')
			.attr('stroke-linecap', 'round')
			.attr('stroke-width', 1.5);

		var defs = this.svg.append("defs")

		defs.append("marker")
			.attr("id", "arrow")
				.attr("viewBox", "0 -5 10 10")
				.attr("refX", 5)
				.attr("refY", 0)
				.attr("markerWidth", 8)
				.attr("markerHeight", 8)
				.attr('fill', 'steelblue')
				.attr("orient", "auto")
			.append("path")
				.attr("d", "M0,-5L10,0L0,5")
				.attr("class","arrowHead");


		this.interact = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')')
			.append('rect')
				.attr('class', 'interact')
				.attr('width', this.width)
				.attr('height', this.height)
				.attr('fill', 'none')
				.attr('pointer-events', 'all')
				.on('mousemove', function(){
					var closest = self.findClosestPoint(d3.event.offsetX - self.margin.left, d3.event.offsetY - self.margin.top);

					if(closest !== null){
						self.updateInfo(closest.data, closest.idx);

						// place a dot on the highlighted point
						self.g.select('circle.highlight-circle')
							.attr('stroke', 'url(#temperature-gradient)')
							.attr('cx', self.x(self.getX(closest.data, closest.idx)))
							.attr('cy', self.y(self.getY(closest.data, closest.idx)))
					}
					else{
						// remove the dot
						self.g.select('circle.highlight-circle')
							.attr('fill', 'none')
							.attr('stroke', 'none')
					}

				})
				.on('click', function(){
					// TODO: Move this to a better button
					self.axis_mode = 1 - self.axis_mode;
					self.draw();
				});


		// 0: admission mode, 1: date mode
		this.axis_mode = 1;

		this.max_contributions = 5;


		this.draw();
	}

	getX(d, i){
		if(this.axis_mode === 0){
			return i;
		}
		else{
			return d.startDate;
		}
	}

	getY(d, i){
		return d.prediction;
	}

	findClosestPoint(x, y){
		var closestDist = +Infinity;
		var closest = null;

		// get distance to each point in screen space
		for(var i in this.data){
			var d = this.data[i];

			var dX = this.x(this.getX(d, i));
			var dY = this.y(this.getY(d, i));

			var dist = Math.sqrt(Math.pow(dX - x, 2) + Math.pow(dY - y, 2));
			if(dist < closestDist){
				closestDist = dist;
				closest = {
					data: d,
					idx: i,
				};

			}
		}

		if(closestDist < 50){
			return closest;
		}

		return null;


	}

	updateInfo(d, data_index){
		var self = this;

		//console.log(d);

		// find top n contributions from the entire 2D array
		var top = [];
		var min_top = -Infinity;

		for(var i = 0; i < d.contributions.length; i++){
			for(var j = 0; j < d.contributions[i].length; j++){
				var c = Math.round(d.contributions[i][j] * 10000) / 10000;

				if(top.length < this.max_contributions || c > min_top){
					top.push({
						'encounterIdx': i,
						'codeIdx': j,
						'contribution': c,
					});

					top.sort(function(a, b){
						return b.contribution - a.contribution;
					});

					min_top = top[top.length - 1].contribution;

					if(top.length >= this.max_contributions){
						top.pop();
					}
				}
			}
		}

		

		//console.log(top, min_top);

		var html = $('<div class="">\
			<div class="">Admission {0}</div>\
			<div class="">Start: {1}</div>\
			<div class="">End: {2}</div>\
			<div class="">Mortality Rating: {3}</div>\
			<div class="contributionContainer"><table></table></div>\
		<div>'.format(i, d3.timeFormat("%Y-%m-%d")(d.startDate), d3.timeFormat("%Y-%m-%d")(d.endDate), d.prediction));

		
		var contributionTable = $('.contributionContainer table', html);

		for(var i = 0; i < top.length; i++){
			var codeData = this.codes[top[i].encounterIdx][top[i].codeIdx];
			var contributionHtml = $('<tr class="contribution">\
				<td class="date">{0}</td>\
				<td class="code">{1}</td>\
				<td class="name">{2}</td>\
				<td class="score">{3}</td>\
			</tr>'.format(d3.timeFormat("%Y-%m-%d")(this.data[top[i].encounterIdx].startDate), codeData.code, 'name', top[i].contribution));

			contributionHtml.on('mouseover', function(event){
				//console.log(this.contributionData, this.sourceId);

				// draw a circle on the target
				var sourceData = self.data[this.sourceId];
				var sourceX = self.x(self.getX(sourceData, this.sourceId));
				var sourceY = self.y(self.getY(sourceData, this.sourceId));

				var encounterData = self.data[this.contributionData.encounterIdx];
				var targetX = self.x(self.getX(encounterData, this.contributionData.encounterIdx));
				var targetY = self.y(self.getY(encounterData, this.contributionData.encounterIdx));

				


				if(this.sourceId !== this.contributionData.encounterIdx){
					// draw source circle
					self.g.select('circle.source-circle')
						.attr('fill', 'steelblue')
						.attr('cx', sourceX)
						.attr('cy', sourceY)

					var midpoints = calcAngledPoint(sourceX, sourceY, targetX, targetY, Math.PI / 2, 1);

					var x_ = midpoints[0];
					var y_ = midpoints[1];

					self.g.select('path.contribution-arrow')
						.attr('stroke', 'steelblue')
						.attr('display', 'show')
						.attr('d', 'M {0},{1} Q {2},{3} {4},{5}'.format(sourceX, sourceY, x_, y_, targetX, targetY));


					// draw arrow from source to target
				}
				else{

					self.g.select('circle.target-circle')
						.attr('fill', 'red')
						.attr('cx', targetX)
						.attr('cy', targetY)
				}



			}.bind({contributionData: top[i], sourceId: parseInt(data_index)}))
			.on('mouseout', function(event){
				self.g.select('circle.source-circle')
					.attr('fill', 'none');

				self.g.select('circle.target-circle')
					.attr('fill', 'none');


				self.g.select('path.contribution-arrow')
					.attr('display', 'none')
			});

			contributionTable.append(contributionHtml);
		}

		this.infoContainer.html(html);
	}

	draw(){

		var self = this;


		this.g.select('circle.highlight-circle')
			.attr('fill', 'none')
			.attr('stroke', 'none')

		// redraw with current axis mode

		if(this.axis_mode === 0){

			this.x.domain([-1, this.data.length]);

			this.g.select('.x-axis')
				.call(
					d3.axisBottom(this.x)
						.tickValues(Array.from(Array(this.data.length).keys()))
						.tickFormat(function(d){ return 'Admission ' + (d + 1);})
				);
		}
		else{

			var xMin = +d3.min(this.data, function(d){ return d.startDate; });
			var xMax = +d3.max(this.data, function(d){ return d.startDate; });

			var range = xMax - xMin;
			xMin = new Date(xMin - 0.1 * range);
			xMax = new Date(xMax + 0.1 * range);


			this.x.domain([xMin, xMax]);

			this.g.select('.x-axis')
				.call(
					d3.axisBottom(this.x)
              		.tickFormat(d3.timeFormat("%Y-%m-%d"))
				);
		}


		this.g.select('path.line')
			.datum(this.data)
			.attr('d', this.line);


	}


}