// plotly.js ships its partial bundles as plain .js with no declarations of
// their own. They expose the same object as the package root, minus the trace
// types they leave out -- which is a runtime difference, not a type one -- so
// borrowing the root's types is accurate for everything the compiler can see.
declare module "plotly.js/dist/plotly-finance" {
  const Plotly: typeof import("plotly.js")
  export default Plotly
}
