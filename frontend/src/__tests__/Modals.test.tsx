import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmModal } from '../components/ConfirmModal';
import { ConfirmDeleteModal } from '../pages/History/ConfirmDeleteModal';
import { LightboxModal } from '../pages/History/LightboxModal';
import { UploadModal } from '../pages/History/UploadModal';
import { type GenerationHistoryEntry } from '../api/client';

describe('ConfirmModal', () => {
  it('renders title, description, and triggers callbacks', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmModal
        isOpen={true}
        title="Confirm action"
        description="Are you sure?"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );

    expect(screen.getByText('Confirm action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(onConfirm).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('ConfirmDeleteModal', () => {
  it('renders and handles confirmation click', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    render(
      <ConfirmDeleteModal
        isOpen={true}
        onClose={onClose}
        onConfirm={onConfirm}
        variant="rejected"
        isPending={false}
      />
    );

    expect(screen.getByText('Delete rejected items?')).toBeInTheDocument();
    
    const deleteBtn = screen.getByRole('button', { name: 'Delete Rejected' });
    fireEvent.click(deleteBtn);
    expect(onConfirm).toHaveBeenCalled();

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('LightboxModal', () => {
  it('renders image preview and details correctly', () => {
    const onClose = vi.fn();
    const mockEntry = {
      task_id: 'task-123',
      title: 'Test Lightbox Title',
      summary: 'A beautiful sunset',
      created_at: '2026-06-19T12:00:00Z',
      output_format: 'jpg',
      source_asset_ids: null,
    } as unknown as GenerationHistoryEntry;

    const mockExif = {
      make: 'Apple',
      model: 'iPhone 15 Pro',
      fileSizeInByte: 2048,
    };

    render(
      <LightboxModal
        isOpen={true}
        imageUrl="http://test.com/img.png"
        entry={mockEntry}
        exif={mockExif}
        onClose={onClose}
      />
    );

    expect(screen.getByAltText('Preview')).toBeInTheDocument();
    expect(screen.getByText('Test Lightbox Title')).toBeInTheDocument();
    expect(screen.getByText('A beautiful sunset')).toBeInTheDocument();
    expect(screen.getByText('Apple iPhone 15 Pro')).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: 'Close' });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('UploadModal', () => {
  it('renders album options and handles confirming', () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    const mockEntry = {
      id: 'task-1',
      title: 'Test Generation',
      album_name: 'AI Photos',
    } as unknown as GenerationHistoryEntry;
    const mockAlbums = [
      { id: 'album-1', album_name: 'AI Photos', asset_count: 5 },
    ];

    render(
      <UploadModal
        isOpen={true}
        onClose={onClose}
        entry={mockEntry}
        albums={mockAlbums}
        onConfirm={onConfirm}
        isPending={false}
      />
    );

    expect(screen.getByText('Upload Destination Album')).toBeInTheDocument();
    
    const confirmBtn = screen.getByRole('button', { name: 'Confirm Upload' });
    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledWith({
      create_album: false,
      album_name: 'AI Photos',
      album_id: 'album-1',
    });
  });
});
