/**
 * CaptiveClone Network Map Module
 * Provides real-time visualization of network clients and access points
 * using D3.js force-directed graph
 */

let networkMap = null;
let simulation = null;
let svg = null;
let nodes = [];
let links = [];
const nodeRadius = 12;
let dragEnabled = true;

/**
 * Initialize the network map
 */
function initNetworkMap() {
  const mapContainer = document.getElementById('networkMapContainer');
  if (!mapContainer) return;
  
  // Set up dimensions
  const width = mapContainer.clientWidth;
  const height = 500;
  
  // Create SVG container
  svg = d3.select('#networkMapContainer')
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('class', 'network-map');
  
  // Create container group for zoom/pan behavior
  const g = svg.append('g');
  
  // Add zoom behavior
  const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform);
    });
  
  svg.call(zoom);
  
  // Create arrow marker for directed links
  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '-0 -5 10 10')
    .attr('refX', nodeRadius + 9)
    .attr('refY', 0)
    .attr('orient', 'auto')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('xoverflow', 'visible')
    .append('svg:path')
    .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
    .attr('fill', '#999')
    .style('stroke', 'none');
  
  // Group for links
  const linkGroup = g.append('g')
    .attr('class', 'links');
  
  // Group for nodes
  const nodeGroup = g.append('g')
    .attr('class', 'nodes');
  
  // Create force simulation
  simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(nodeRadius * 1.5));
  
  // Store the network map object
  networkMap = {
    svg: svg,
    linkGroup: linkGroup,
    nodeGroup: nodeGroup,
    width: width,
    height: height
  };
  
  // Initial data load
  fetchNetworkData();
  
  // Set up periodic updates
  setInterval(fetchNetworkData, 5000);
}

/**
 * Fetch network data from the server
 */
function fetchNetworkData() {
  fetch('/api/network-map')
    .then(response => response.json())
    .then(data => updateNetworkMap(data))
    .catch(error => console.error('Error fetching network map data:', error));
}

/**
 * Update the network map with fresh data
 * @param {Object} data - Network map data
 */
function updateNetworkMap(data) {
  if (!networkMap) return;
  
  // Update nodes and links
  nodes = data.nodes;
  links = data.links;
  
  // Update the visualization
  renderNetworkMap();
}

/**
 * Render the network map with current data
 */
function renderNetworkMap() {
  if (!networkMap) return;
  
  const { linkGroup, nodeGroup } = networkMap;
  
  // Update links
  const link = linkGroup.selectAll('.link')
    .data(links, d => `${d.source}-${d.target}`);
    
  link.exit().remove();
  
  const linkEnter = link.enter()
    .append('line')
    .attr('class', 'link')
    .attr('stroke', '#999')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', d => d.value || 1)
    .attr('marker-end', 'url(#arrowhead)');
  
  // Update nodes
  const node = nodeGroup.selectAll('.node')
    .data(nodes, d => d.id);
    
  node.exit().remove();
  
  const nodeEnter = node.enter()
    .append('g')
    .attr('class', 'node')
    .call(setupDragBehavior());
  
  // Add circles for each node
  nodeEnter.append('circle')
    .attr('r', nodeRadius)
    .attr('fill', d => getNodeColor(d))
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5);
  
  // Add labels
  nodeEnter.append('text')
    .attr('dy', -nodeRadius - 5)
    .attr('text-anchor', 'middle')
    .text(d => d.name || d.id)
    .attr('font-size', '12px')
    .attr('fill', '#333');
  
  // Setup tooltips
  nodeEnter.append('title')
    .text(d => {
      let tooltip = `ID: ${d.id}\nType: ${d.type}`;
      if (d.type === 'ap') {
        tooltip += `\nSSID: ${d.name || 'Unknown'}`;
        tooltip += `\nChannel: ${d.channel || 'N/A'}`;
        tooltip += `\nConnected clients: ${d.clientCount || 0}`;
      } else if (d.type === 'client') {
        tooltip += `\nMAC: ${d.mac || 'Unknown'}`;
        tooltip += `\nConnected to: ${d.connected_to || 'None'}`;
        tooltip += `\nStatus: ${d.status || 'Unknown'}`;
      }
      return tooltip;
    });
  
  // Update simulation
  simulation.nodes(nodes)
    .on('tick', () => {
      // Update link positions
      linkGroup.selectAll('.link')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      
      // Update node positions
      nodeGroup.selectAll('.node')
        .attr('transform', d => `translate(${d.x},${d.y})`);
    });
  
  // Update link force
  simulation.force('link').links(links);
  
  // Restart the simulation
  simulation.alpha(0.3).restart();
}

/**
 * Get color for a node based on its type
 * @param {Object} node - The node object
 * @return {string} - Color code
 */
function getNodeColor(node) {
  switch (node.type) {
    case 'ap':
      return node.is_target ? '#ff7f0e' : '#1f77b4';
    case 'client':
      switch (node.status) {
        case 'connected': return '#2ca02c';
        case 'disconnected': return '#d62728';
        case 'captured': return '#8c564b';
        case 'deauthenticating': return '#ff9896';
        default: return '#7f7f7f';
      }
    default:
      return '#7f7f7f';
  }
}

/**
 * Set up drag behavior for nodes
 */
function setupDragBehavior() {
  return d3.drag()
    .on('start', (event, d) => {
      if (!dragEnabled) return;
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on('drag', (event, d) => {
      if (!dragEnabled) return;
      d.fx = event.x;
      d.fy = event.y;
    })
    .on('end', (event, d) => {
      if (!dragEnabled) return;
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    });
}

/**
 * Toggle node dragging
 * @param {boolean} enabled - Whether dragging should be enabled
 */
function toggleDrag(enabled) {
  dragEnabled = enabled;
}

/**
 * Export the network map as PNG
 */
function exportNetworkMap() {
  if (!networkMap) return;
  
  // Convert SVG to canvas using SVG serialization and canvas drawing
  const svgString = new XMLSerializer().serializeToString(networkMap.svg.node());
  const canvas = document.createElement('canvas');
  canvas.width = networkMap.width;
  canvas.height = networkMap.height;
  const ctx = canvas.getContext('2d');
  
  // Create an image from the SVG string
  const img = new Image();
  const svgBlob = new Blob([svgString], {type: 'image/svg+xml;charset=utf-8'});
  const url = URL.createObjectURL(svgBlob);
  
  img.onload = function() {
    // Draw white background
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw the image
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    
    // Create download link
    const link = document.createElement('a');
    link.download = `captiveclone-network-map-${new Date().toISOString()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };
  
  img.src = url;
}

// Initialize network map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('networkMapContainer')) {
    // Dynamically load D3.js from CDN
    const script = document.createElement('script');
    script.src = 'https://d3js.org/d3.v7.min.js';
    script.onload = initNetworkMap;
    document.head.appendChild(script);
  }
}); 