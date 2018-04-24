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

// Returns an attrTween for translating along the specified path element.
function translateAlong(path) {
	var l = path.getTotalLength();
	var ps = path.getPointAtLength(0);
	var pe = path.getPointAtLength(l);
	var angl = Math.atan2(pe.y - ps.y, pe.x - ps.x) * (180 / Math.PI) - 90;
	var rot_tran = "rotate(" + angl + ")";
	return function(d, i, a) {
		return function(t) {
			var p = path.getPointAtLength(t * l);
			return "translate(" + p.x + "," + p.y + ") " + rot_tran;
		};
	};
}

class Chart{
	constructor(data, codes, element, infoContainer, observationContainer){
		console.log('connecting the chart 2');
		var self = this;

		this.data = data;
		this.codes = codes;
		this.observationData = null;
		this.svg = d3.select(element[0]);
		this.infoContainer = infoContainer;
		this.observationContainer = observationContainer;

		this.margin = {top: 20, right: 20, bottom: 30, left: 50};
		this.width = +this.svg.attr('width') - this.margin.left - this.margin.right;
		this.height = +this.svg.attr('height') - this.margin.top - this.margin.bottom;
		this.g0 = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');
		this.g = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');
		this.g2 = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');
		
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
				{offset: '0%', color: '#a80000', opacity: 0},
				{offset: '100%', color: '#a80000', opacity: 1}
			])
		.enter().append('stop')
			.attr('offset', function(d) { return d.offset; })
			.attr('stop-color', function(d) { return d.color; })
			.attr('stop-opacity', function(d) { return d.opacity; });

		this.svg.append('linearGradient')
			.attr('id', 'line-gradient')
			.attr('gradientUnits', 'userSpaceOnUse')
			.attr('x1', 0).attr('y1', this.y(0))
			.attr('x2', 0).attr('y2', this.y(1))
		.selectAll('stop')
			.data([
				{offset: '0%', color: 'grey', opacity: 0.5},
				{offset: '100%', color: '#800823', opacity: 1}
			])
		.enter().append('stop')
			.attr('offset', function(d) { return d.offset; })
			.attr('stop-color', function(d) { return d.color; })
			.attr('stop-opacity', function(d) { return d.opacity; });

		
		
		this.g.append('g')
			.attr('transform', 'translate(0,' + this.height + ')')
			.attr('class', 'x-axis')

		this.g.append('g')
			.call(d3.axisLeft(this.y))
		.append('text')
			.attr('fill', '#000')
			//.attr('transform', 'rotate(-90)')
			.attr('x', 5)
			.attr('y', 0)
			.attr('dy', '1em')
			.attr('font-size', '2em')
			.attr('text-anchor', 'start')
			.text('Mortality Risk');

		this.g0.append('g')
			.attr('class', 'grid')
			.call(
				d3.axisLeft(this.y)
				.ticks(5)
				.tickFormat('')
				.tickSize(-this.width)
			)
			.select('.domain').remove();

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

		this.g.append('circle')
			.attr('class', 'pulse-circle-1')
			.attr('fill', 'none')
			.attr('stroke', 'none')
			.attr('stroke-width', 1.5)
			.attr('r', 10);

		this.g.append('circle')
			.attr('class', 'pulse-circle-2')
			.attr('fill', 'none')
			.attr('stroke', 'none')
			.attr('stroke-width', 1.5)
			.attr('r', 10);

		this.g2.append('path')
			.attr('class', 'contribution-arrow')
			.attr('fill', 'none')
			.attr('stroke-linejoin', 'round')
			.attr('stroke-linecap', 'round')
			.attr('stroke-width', 1.5);

		this.g2.append("svg:path")
			.attr("d", function(d){ return d3.symbol().type(d3.symbolTriangle).size(40)(); })
			.attr('class', 'arrow-head')
			.attr('display', 'none');

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
						
						self.closestPoint = closest;

						// place a dot on the highlighted point
						self.g.select('circle.highlight-circle')
							//.attr('stroke', 'url(#temperature-gradient)')
							.attr('stroke', 'grey')
							.attr('cx', self.x(self.getX(closest.data, closest.idx)))
							.attr('cy', self.y(self.getY(closest.data, closest.idx)))

						self.showTooltip([
							[
								{
									text: 'Mortality Risk',
									style: {'font-size': '1.5em'}
								},
							],
							[
								{
									text: closest.data.prediction,
									style: {'font-size': '1.2em', 'padding-bottom': '5px'}
								},
							],
							[
								{
									text: '{0} - {1}'.format(d3.timeFormat("%m/%d/%Y")(closest.data.startDate), d3.timeFormat("%m/%d/%Y")(closest.data.endDate)),
									style: {'font-size': '1em'}
								},
							],
						], {left: d3.event.pageX + 20, top: d3.event.pageY - 5})


						// display tooltip 
					}
					else{

						self.closestPoint = null;
						self.hideTooltip();

						// remove the dot
						self.g.select('circle.highlight-circle')
							.attr('fill', 'none')
							.attr('stroke', 'none')
					}

				})
				.on('mouseleave', function(){
					self.closestPoint = null;
					self.hideTooltip();

					// remove the dot
					self.g.select('circle.highlight-circle')
						.attr('fill', 'none')
						.attr('stroke', 'none')
				})
				.on('click', function(){
					// TODO: Move this to a better button

					if(self.closestPoint !== null){
						self.updateInfo(self.closestPoint.data, self.closestPoint.idx);
						self.max_contributions = 8;
						self.drawContributionInfo();
						self.drawObservationInfo();


						// display pulse on the target point
						self.pulse(self.x(self.getX(self.closestPoint.data, self.closestPoint.idx)), self.y(self.getY(self.closestPoint.data, self.closestPoint.idx)));
						

					}

					//self.axis_mode = 1 - self.axis_mode;
					//self.draw();
				});


		// 0: admission mode, 1: date mode
		this.axis_mode = 1;

		this.max_contributions = 8;
		this.min_contributions = 0;

		this.closestPoint = null;
		this.currentContributionArrow = null;

		this.infoData = null;


		this.draw();
	}

	showTooltip(data, options){

		var html = '';

		for(var i = 0; i < data.length; i++){
			html += '<tr>'
			for(var j = 0; j < data[i].length; j++){
				var element = data[i][j];
				var text = element.text;

				var style = '';
				for(var key in element.style){
					style += key + ': ' + element.style[key] + ';';
				}

				html += '<td style="' + style + '">' + text + '</td>';
			}
			html += '</tr>'
		}

		html = '<div><table>' + html + '</table></div>';
		var tooltip = $('#tooltip');

		tooltip.html(html);

		
		//var placement = this.adjustPlacement(tooltip, options);

		tooltip.show();
		tooltip.css({
			'left': options.left, 
			'top': options.top,
		});
	}

	hideTooltip(){
		$('#tooltip').hide();
	}

	setObservationData(data){
		this.observationData = data;

		// update side bar if necessary
		//this.drawContributionInfo();
		this.drawObservationInfo();
	}

	pulse(x, y){
		this.g.select('circle.pulse-circle-1')
			.attr('fill', 'none')
			.attr('stroke', 'red')
			.attr('cx', x)
			.attr('cy', y)
			//.attr('r', 0)
		.transition()
			.duration(700)
			.attrTween('r', function(){
				return function(t){
					return t * 50;
				}
			})
			.attrTween('opacity', function(){
				return function(t){
					return 1 - t;
				}
			});

		this.g.select('circle.pulse-circle-2')
			.attr('fill', 'none')
			.attr('stroke', 'red')
			.attr('cx', x)
			.attr('cy', y)
			//.attr('r', 0)
		.transition()
			.duration(700)
			.delay(100)
			.attrTween('r', function(){
				return function(t){
					return t * 50;
				}
			})
			.attrTween('opacity', function(){
				return function(t){
					return 1 - t;
				}
			});
	}

	getX(d, i){
		if(this.axis_mode === 0){
			return d.idx;
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


	displayContributionArrow(sourceId, contributionData){
		var self = this;
		// draw a circle on the target
		var sourceData = self.data[sourceId];
		var sourceX = self.x(self.getX(sourceData, sourceId));
		var sourceY = self.y(self.getY(sourceData, sourceId));

		var encounterData = self.data[contributionData.encounterIdx];
		var targetX = self.x(self.getX(encounterData, contributionData.encounterIdx));
		var targetY = self.y(self.getY(encounterData, contributionData.encounterIdx));

		if(sourceId !== contributionData.encounterIdx){
			// draw source circle
			//self.g.select('circle.source-circle')
			//	.attr('fill', 'steelblue')
			//	.attr('cx', sourceX)
			//	.attr('cy', sourceY)

			var midpoints = calcAngledPoint(sourceX, sourceY, targetX, targetY, Math.PI / 2, 1);

			var x_ = midpoints[0];
			var y_ = midpoints[1];

			var arrow = self.g2.select('path.contribution-arrow')
				.attr('stroke', 'url(#line-gradient')
				.attr('display', 'show')
				.attr('d', 'M {0},{1} Q {2},{3} {4},{5}'.format(sourceX, sourceY, x_, y_, targetX, targetY));


			var transition_duration = 500;

			self.g2.select('path.arrow-head')
				.attr('display', 'show')
				.attr('fill', 'url(#line-gradient')
				.transition()
					.duration(transition_duration)
					.attrTween("transform", translateAlong(arrow.node()))

			var totalLength = arrow.node().getTotalLength();

			arrow
				.attr("stroke-dasharray", totalLength + " " + totalLength)
				//.attr("stroke-dashoffset", totalLength)
			.transition()
				.duration(transition_duration)
				.attrTween('stroke-dashoffset', function() {
					return function(t){
						return (1 - t) * totalLength;
					}
				});


			// draw arrow from source to target
		}
		else{

			self.g.select('circle.target-circle')
				.attr('fill', 'red')
				.attr('cx', targetX)
				.attr('cy', targetY)

			self.pulse(targetX, targetY);
		}
	}

	clearContributionArrow(){
		this.g.select('circle.source-circle')
			.attr('fill', 'none');

		this.g.select('circle.target-circle')
			.attr('fill', 'none');

		this.g2.select('path.contribution-arrow')
			.attr('display', 'none')

		this.g2.select('path.arrow-head')
			.attr('display', 'none');
	}

	updateInfo(d, data_index){
		this.infoData = {d: d, index: data_index};
	}


	drawContributionInfo(){
		var self = this;

		if(this.infoData === null){
			return;
		}

		var d = this.infoData.d;
		var data_index = this.infoData.index;

		// find top n contributions from the entire 2D array
		var contributionData = [];

		for(var i = 0; i < d.contributions.length; i++){
			for(var j = 0; j < d.contributions[i].length; j++){
				var c = Math.round(d.contributions[i][j] * 10000) / 10000;

				contributionData.push({
					'encounterIdx': i,
					'encounterId': this.data[i].ID,
					'codeIdx': j,
					'contribution': c,
				});
			}
		}

		var num_contributions = contributionData.length;

		contributionData.sort(function(a, b){
			return b.contribution - a.contribution;
		});

		if(this.max_contributions + this.min_contributions < contributionData.length){
			contributionData.splice(this.max_contributions, contributionData.length - (this.max_contributions + this.min_contributions));
		}

		var html = $('<div class="">\
			<div class="">Admission {0}</div>\
			<div class="">{1} - {2}</div>\
			<div class="">Mortality Risk: {3}</div>\
			<div class="contributionContainer">\
				<table class="contributionTable">\
					<tr class="contribution">\
						<td class="score">Contribution</td>\
						<td class="code">ICD-9</td>\
						<td class="name">Name</td>\
					</tr>\
				</table>\
				<div class="contributionButtonContainer">\
					<button class="lessButton contributionButton">Show Less</button>\
					<button class="moreButton contributionButton">Show More</button>\
				</div>\
			</div>\
		<div>'.format(i, d3.timeFormat("%m/%d/%Y")(d.startDate), d3.timeFormat("%m/%d/%Y")(d.endDate), d.prediction));

		if(this.max_contributions <= 8	){
			$('button.lessButton', html).attr('disabled', true);
		}
		if(this.max_contributions >= num_contributions){
			$('button.moreButton', html).attr('disabled', true);
		}


		$('button.lessButton', html).on('click', function(event){
			self.max_contributions = 8;
			self.drawContributionInfo();
		});

		$('button.moreButton', html).on('click', function(event){
			self.max_contributions = Math.min(self.max_contributions + 5, num_contributions);
			self.drawContributionInfo();
		});
		
		var contributionTable = $('.contributionContainer table', html);

		for(var i = 0; i < contributionData.length; i++){
			var codeData = this.codes[contributionData[i].encounterId][contributionData[i].codeIdx];
			var contributionHtml = $('<tr class="contribution">\
				<td class="score">{0}</td>\
				<td class="code">{1}</td>\
				<td class="name">{2}</td>\
			</tr>'.format(contributionData[i].contribution, codeData.code, codeData.name));

			$('.score', contributionHtml).css({
				'background-color': d3.interpolateRdBu(-contributionData[i].contribution * 0.5 + 0.5),
				'color': Math.abs(contributionData[i].contribution) > 0.5 ? 'white' : 'black',
			});

			contributionHtml.on('mouseenter', function(event){
				event.stopPropagation();
				self.displayContributionArrow(this.sourceId, this.contributionData);

			}.bind({contributionData: contributionData[i], sourceId: parseInt(data_index)}))
			.on('mouseleave', function(event){
				event.stopPropagation();
				self.clearContributionArrow();
			})
			.on('click', function(event){
				// lock the arrow display to the current one
				self.currentContributionArrow = true;
				self.displayContributionArrow(this.sourceId, this.contributionData);

			}.bind({contributionData: contributionData[i], sourceId: parseInt(data_index)}));

			contributionTable.append(contributionHtml);
		}

		this.infoContainer.html(html);
	}

	drawObservationInfo(){
		var self = this;

		if(this.infoData === null){
			return;
		}

		var d = this.infoData.d;
		var data_index = this.infoData.index;

		var observationHtml = $('<table class="observationTable"></table>');

		if(this.observationData === null){
			observationHtml = 'Loading Observation Data';
		}
		else{
			var encounterId = this.data[parseInt(data_index)].ID;

			var obsData = this.observationData[encounterId];

			observationHtml.append('<tr>\
				<td class="code">Loinc</td>\
				<td class="name">Name</td>\
				<td class="value">Value</td>\
				<td class="units">Units</td>\
			</tr>');

			for(var i = 0; obsData !== undefined && i < obsData.length; i++){

				if(obsData[i].system !== 'http://loinc.org'){
					// only display loinc codes for now
					continue;
				}

				observationHtml.append('<tr>\
					<td class="code">{0}</td>\
					<td class="name">{1}</td>\
					<td class="value">{2}</td>\
					<td class="units">{3}</td>\
				</tr>'.format(obsData[i].code, obsData[i].name, obsData[i].value, obsData[i].units !== 'No matching concept' ? obsData[i].units : ''));
			}
		}

		this.observationContainer.html(observationHtml);
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
              		.tickFormat(d3.timeFormat("%m/%d/%Y"))
				);
		}

		var lineData = [];
		var first = Object.assign({}, this.data[0]);
		var last = Object.assign({}, this.data[this.data.length - 1]);

		first.prediction = 0;
		last.prediction = 0;

		lineData.push(first);
		lineData.push(...this.data);
		lineData.push(last);


		var path = this.g.select('path.line')
			.datum(lineData)
			.attr('d', this.line);

//		var totalLength = path.node().getTotalLength();
//
//		path
//			.attr("stroke-dasharray", totalLength + " " + totalLength)
//			.attr("stroke-dashoffset", totalLength)
//		.transition()
//			.attr("stroke-dashoffset", 0);

		this.g.selectAll('circle.line-corners')
			.data(this.data)
		.enter().append('circle')
			.attr('class', 'line-corners');
			
		this.g.selectAll('circle.line-corners')
			.data(this.data)
			.attr('cx', function(d, i){ return self.x(self.getX(d, i)); })
			.attr('cy', function(d, i){ return self.y(self.getY(d, i)); })
			.attr('r', 5)
			.attr('fill', 'white')
			//.attr('stroke', 'url(#temperature-gradient)')
			.attr('stroke', 'grey')
			.attr('stroke-width', 1.5);

		this.g.selectAll('circle.line-corners')
			.data(this.data)
		.exit().remove();


	}


}