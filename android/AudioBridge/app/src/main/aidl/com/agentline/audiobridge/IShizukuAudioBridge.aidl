package com.agentline.audiobridge;

interface IShizukuAudioBridge {
    void startRecord(int port);
    void stopRecord();
    boolean isRecording();
    void destroy();
}
