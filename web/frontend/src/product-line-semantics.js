export function bindProductLine(element, productLine, surface) {
  if (productLine) {
    element.dataset.productLine = productLine
    element.dataset.productSurface = surface
  } else {
    delete element.dataset.productLine
    delete element.dataset.productSurface
  }
  return element
}
