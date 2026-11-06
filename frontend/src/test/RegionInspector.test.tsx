import { expect,it,vi } from 'vitest'
import { render,screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RegionInspector from '../components/RegionInspector'
import type { Result } from '../types'

vi.mock('../api',()=>({artifactUrl:(url:string)=>url}))
vi.mock('../components/ImageCompare',()=>({default:({region}:{region?:object})=><div data-testid="crop">{JSON.stringify(region??null)}</div>}))

it('shows detected image regions and updates the before/after crop',async()=>{
  const user=userEvent.setup();const region={x:.1,y:.2,width:.3,height:.4}
  const result={artifacts:{original:'/before.png',enhanced:'/after.png'},diagnostics:[{problem:'Detected edge risk',region}]} as unknown as Result
  render(<RegionInspector result={result}/>);await user.selectOptions(screen.getByLabelText('Inspection region'),'risk-0')
  expect(screen.getByTestId('crop')).toHaveTextContent(JSON.stringify(region))
  await user.selectOptions(screen.getByLabelText('Inspection region'),'full');expect(screen.getByTestId('crop')).toHaveTextContent('null')
})
