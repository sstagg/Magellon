interface InfoLineProps {
    icon: React.ReactNode;
    caption: string;
    value: React.ReactNode;
}
export const InfoLineComponent: React.FC<InfoLineProps> = ({ icon, caption, value }) => {
    const rootStyle: React.CSSProperties = {
        fontFamily: 'Exo 2, Arial, sans-serif',
        display: 'flex',
        alignItems: 'center',
        // justifyContent: 'space-between',
        margin: 5,
    };
    const iconStyle: React.CSSProperties = {
        fontSize: '1.5rem',
        display:"none",
        marginRight: 1,
    };
    const captionStyle: React.CSSProperties = {
        fontFamily: 'Exo 2, Arial, sans-serif',
        fontWeight: 'bold',
        minWidth:100,

        // marginRight: theme.spacing(1),
    };
    const valueStyle: React.CSSProperties = {
        minWidth:100,
        fontSize: '1rem',
        // marginRight: theme.spacing(1),
    };

    return (
        <div style={rootStyle}>
            <span style={iconStyle}>{icon}</span>
            <span className='captionStyle'> {caption}: </span>
            <span style={valueStyle}> {value}</span>
        </div>
    );
};

