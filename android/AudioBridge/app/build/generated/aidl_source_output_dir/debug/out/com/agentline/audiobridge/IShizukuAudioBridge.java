/*
 * This file is auto-generated.  DO NOT MODIFY.
 */
package com.agentline.audiobridge;
public interface IShizukuAudioBridge extends android.os.IInterface
{
  /** Default implementation for IShizukuAudioBridge. */
  public static class Default implements com.agentline.audiobridge.IShizukuAudioBridge
  {
    @Override public void startRecord(int port) throws android.os.RemoteException
    {
    }
    @Override public void stopRecord() throws android.os.RemoteException
    {
    }
    @Override public boolean isRecording() throws android.os.RemoteException
    {
      return false;
    }
    @Override public void destroy() throws android.os.RemoteException
    {
    }
    @Override
    public android.os.IBinder asBinder() {
      return null;
    }
  }
  /** Local-side IPC implementation stub class. */
  public static abstract class Stub extends android.os.Binder implements com.agentline.audiobridge.IShizukuAudioBridge
  {
    /** Construct the stub at attach it to the interface. */
    public Stub()
    {
      this.attachInterface(this, DESCRIPTOR);
    }
    /**
     * Cast an IBinder object into an com.agentline.audiobridge.IShizukuAudioBridge interface,
     * generating a proxy if needed.
     */
    public static com.agentline.audiobridge.IShizukuAudioBridge asInterface(android.os.IBinder obj)
    {
      if ((obj==null)) {
        return null;
      }
      android.os.IInterface iin = obj.queryLocalInterface(DESCRIPTOR);
      if (((iin!=null)&&(iin instanceof com.agentline.audiobridge.IShizukuAudioBridge))) {
        return ((com.agentline.audiobridge.IShizukuAudioBridge)iin);
      }
      return new com.agentline.audiobridge.IShizukuAudioBridge.Stub.Proxy(obj);
    }
    @Override public android.os.IBinder asBinder()
    {
      return this;
    }
    @Override public boolean onTransact(int code, android.os.Parcel data, android.os.Parcel reply, int flags) throws android.os.RemoteException
    {
      java.lang.String descriptor = DESCRIPTOR;
      if (code >= android.os.IBinder.FIRST_CALL_TRANSACTION && code <= android.os.IBinder.LAST_CALL_TRANSACTION) {
        data.enforceInterface(descriptor);
      }
      switch (code)
      {
        case INTERFACE_TRANSACTION:
        {
          reply.writeString(descriptor);
          return true;
        }
      }
      switch (code)
      {
        case TRANSACTION_startRecord:
        {
          int _arg0;
          _arg0 = data.readInt();
          this.startRecord(_arg0);
          reply.writeNoException();
          break;
        }
        case TRANSACTION_stopRecord:
        {
          this.stopRecord();
          reply.writeNoException();
          break;
        }
        case TRANSACTION_isRecording:
        {
          boolean _result = this.isRecording();
          reply.writeNoException();
          reply.writeInt(((_result)?(1):(0)));
          break;
        }
        case TRANSACTION_destroy:
        {
          this.destroy();
          reply.writeNoException();
          break;
        }
        default:
        {
          return super.onTransact(code, data, reply, flags);
        }
      }
      return true;
    }
    private static class Proxy implements com.agentline.audiobridge.IShizukuAudioBridge
    {
      private android.os.IBinder mRemote;
      Proxy(android.os.IBinder remote)
      {
        mRemote = remote;
      }
      @Override public android.os.IBinder asBinder()
      {
        return mRemote;
      }
      public java.lang.String getInterfaceDescriptor()
      {
        return DESCRIPTOR;
      }
      @Override public void startRecord(int port) throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          _data.writeInt(port);
          boolean _status = mRemote.transact(Stub.TRANSACTION_startRecord, _data, _reply, 0);
          _reply.readException();
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
      }
      @Override public void stopRecord() throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          boolean _status = mRemote.transact(Stub.TRANSACTION_stopRecord, _data, _reply, 0);
          _reply.readException();
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
      }
      @Override public boolean isRecording() throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        boolean _result;
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          boolean _status = mRemote.transact(Stub.TRANSACTION_isRecording, _data, _reply, 0);
          _reply.readException();
          _result = (0!=_reply.readInt());
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
        return _result;
      }
      @Override public void destroy() throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          boolean _status = mRemote.transact(Stub.TRANSACTION_destroy, _data, _reply, 0);
          _reply.readException();
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
      }
    }
    static final int TRANSACTION_startRecord = (android.os.IBinder.FIRST_CALL_TRANSACTION + 0);
    static final int TRANSACTION_stopRecord = (android.os.IBinder.FIRST_CALL_TRANSACTION + 1);
    static final int TRANSACTION_isRecording = (android.os.IBinder.FIRST_CALL_TRANSACTION + 2);
    static final int TRANSACTION_destroy = (android.os.IBinder.FIRST_CALL_TRANSACTION + 3);
  }
  public static final java.lang.String DESCRIPTOR = "com.agentline.audiobridge.IShizukuAudioBridge";
  public void startRecord(int port) throws android.os.RemoteException;
  public void stopRecord() throws android.os.RemoteException;
  public boolean isRecording() throws android.os.RemoteException;
  public void destroy() throws android.os.RemoteException;
}
