import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ImageCompare from '../components/ImageCompare'

beforeEach(()=>{
  vi.stubGlobal('ResizeObserver',class {observe(){}disconnect(){}})
  vi.stubGlobal('Image',class {
    width=128;height=96;onload:(()=>void)|null=null
    set src(_value:string){queueMicrotask(()=>this.onload?.())}
  })
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({scale:vi.fn(),clearRect:vi.fn(),drawImage:vi.fn(),save:vi.fn(),beginPath:vi.fn(),rect:vi.fn(),clip:vi.fn(),restore:vi.fn(),fillRect:vi.fn()} as unknown as CanvasRenderingContext2D)
})
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks()})
it('supports a comparison slider, side by side, and zoom controls',async()=>{
  const user=userEvent.setup();render(<ImageCompare original="/before.png" enhanced="/after.png"/>)
  expect(screen.getByRole('img')).toHaveAccessibleName('Original and restored image comparison')
  const slider=screen.getByRole('slider',{name:'Before and after comparison'})
  slider.focus();await user.keyboard('{ArrowRight}'); // The native range remains keyboard focusable.
  await user.click(screen.getByRole('button',{name:'Side by side'}))
  expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'Zoom in'}));expect(screen.getByText('125%')).toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'Reset view'}));expect(screen.getByText('100%')).toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'Slider'}));expect(screen.getByRole('slider')).toBeInTheDocument()
})
