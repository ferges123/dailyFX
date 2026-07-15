import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { StatusTile } from '../components/StatusTile';
import { Field, SelectField } from '../components/Field';
import { FilterRow, ModuleConfigEditor } from '../components/EffectsComponents';
import { type GenerationModuleInfo } from '../api/client';

describe('StatusTile', () => {
  it('renders status tiles with detailed descriptors', () => {
    render(
      <StatusTile
        icon={<span data-testid="status-icon">Icon</span>}
        label="Usage limit"
        value="10%"
        detail="Remaining space details"
        tone="success"
      />,
    );

    expect(screen.getByTestId('status-icon')).toBeInTheDocument();
    expect(screen.getByText('Usage limit')).toBeInTheDocument();
    expect(screen.getByText('10%')).toBeInTheDocument();
    expect(screen.getByText('Remaining space details')).toBeInTheDocument();
  });
});

describe('Field and SelectField', () => {
  it('renders inputs with error labels', () => {
    const onChange = vi.fn();
    render(
      <Field
        label="Username"
        value="john_doe"
        onChange={onChange}
        error="Name contains forbidden characters"
      />,
    );

    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(
      screen.getByText('Name contains forbidden characters'),
    ).toBeInTheDocument();

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'jane' } });
    expect(onChange).toHaveBeenCalled();
  });

  it('renders SelectField options', () => {
    render(
      <SelectField label="Model Choice" defaultValue="gpt-4">
        <option value="gpt-4">GPT 4</option>
        <option value="gpt-3.5">GPT 3.5</option>
      </SelectField>,
    );

    expect(screen.getByText('Model Choice')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('gpt-4');
  });
});

describe('FilterRow', () => {
  it('triggers change handlers on select toggle or weight adjustment', () => {
    const onEnabledChange = vi.fn();
    const onWeightChange = vi.fn();

    render(
      <table>
        <tbody>
          <FilterRow
            title="Saturation Filter"
            icon={null}
            enabled={false}
            weight={50}
            config={<div>Config Node</div>}
            onEnabledChange={onEnabledChange}
            onWeightChange={onWeightChange}
          />
        </tbody>
      </table>,
    );

    expect(screen.getByText('Saturation Filter')).toBeInTheDocument();
    expect(screen.getByText('Config Node')).toBeInTheDocument();

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(onEnabledChange).toHaveBeenCalledWith(true);

    const weightInput = screen.getByRole('spinbutton');
    fireEvent.change(weightInput, { target: { value: '80' } });
    expect(onWeightChange).toHaveBeenCalledWith(80);
  });
});

describe('ModuleConfigEditor', () => {
  it('renders configuration inputs dynamically from metadata schema', () => {
    const onChange = vi.fn();
    const mockModule = {
      name: 'test_module',
      label: 'Test Module',
      description: 'Module for testing',
      enabled: true,
      weight: 1.0,
      config: {},
      config_schema: [
        {
          key: 'steps',
          label: 'Steps Count',
          type: 'number',
          default: 20,
          min: 1,
          max: 100,
        },
        {
          key: 'prompt_style',
          label: 'Prompt Style',
          type: 'select',
          default: 'vivid',
          options: [
            { label: 'Vivid Style', value: 'vivid' },
            { label: 'Natural Style', value: 'natural' },
          ],
        },
      ],
    } as unknown as GenerationModuleInfo;

    render(
      <ModuleConfigEditor
        module={mockModule}
        config={{ steps: 20, prompt_style: 'vivid' }}
        onChange={onChange}
      />,
    );

    expect(screen.getByText('Steps Count')).toBeInTheDocument();
    expect(screen.getByText('Prompt Style')).toBeInTheDocument();

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'natural' } });
    expect(onChange).toHaveBeenCalledWith('prompt_style', 'natural');
  });

  it('renders checkbox inputs for boolean fields', () => {
    const onChange = vi.fn();
    const mockModule = {
      name: 'test_module_bool',
      label: 'Test Module Bool',
      description: 'Module for testing boolean config',
      enabled: true,
      weight: 1.0,
      config: {},
      config_schema: [
        {
          key: 'enable_feature',
          label: 'Enable Feature',
          type: 'boolean',
          default: true,
        },
      ],
    } as unknown as GenerationModuleInfo;

    render(
      <ModuleConfigEditor
        module={mockModule}
        config={{ enable_feature: true }}
        onChange={onChange}
      />,
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith('enable_feature', false);
  });
});
